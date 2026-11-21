"""Shared recommendation features must yield identical interactive/worker scores."""

from decimal import Decimal
from uuid import uuid4

from domain_fixtures import make_brand, make_collection_item, make_fragrance, make_user
from sqlalchemy.orm import Session

from scentiq_api.services.recommendation_scoring import positive_taste_overlap


def test_positive_taste_overlap_rejects_negative_and_weights_unrated_ownership() -> None:
    assert positive_taste_overlap({"smoky": 1}, set(), {"smoky"}, set(), {"accord:smoky": -1}) == 0
    assert positive_taste_overlap({"smoky": 1}, set(), {"smoky"}, set(), {}) == 0.5
    assert positive_taste_overlap({"floral": 1}, set(), set(), set(), {"accord:floral": 1}) == 1


def test_worker_and_interactive_scores_match_with_personal_taste(session: Session) -> None:
    from scentiq_api.hybrid.contracts import RecommendationJobInput
    from scentiq_api.hybrid.processor import _discovery, _layering
    from scentiq_api.hybrid.runtime import _hybrid_fragrance
    from scentiq_api.models import Accord, FragranceAccord
    from scentiq_api.repositories import DiscoveryRepository, LayeringRepository
    from scentiq_api.services.discovery import DiscoveryService
    from scentiq_api.services.layering import LayeringService
    from scentiq_api.services.taste_profile import TasteProfileService

    user = make_user(session, email="worker-parity@example.test")
    brand = make_brand(session, name="Worker Parity")
    liked = make_fragrance(session, brand=brand, name="Liked", seasons=("summer",))
    disliked = make_fragrance(session, brand=brand, name="Disliked", seasons=("summer",))
    candidate = make_fragrance(session, brand=brand, name="Candidate", seasons=("summer",))
    accord = Accord(name="Floral", slug="floral")
    session.add(accord)
    session.flush()
    for scent in (liked, candidate):
        session.add(
            FragranceAccord(fragrance_id=scent.id, accord_id=accord.id, weight=Decimal("1"))
        )
    make_collection_item(session, user=user, fragrance=liked, user_rating=5)
    make_collection_item(session, user=user, fragrance=disliked, user_rating=1)
    session.flush()
    profile = TasteProfileService(session).for_user(user.id)
    owned = LayeringRepository(session).owned(user.id)
    request = RecommendationJobInput(
        job_id=uuid4(),
        input_version=1,
        catalog_version="v1",
        collection=[],
        owned=[_hybrid_fragrance(item) for item in owned],
        candidates=[_hybrid_fragrance(candidate)],
        taste_features=profile.features,
        profile_version=profile.version,
    )
    actual = DiscoveryService(DiscoveryRepository(session)).discover(user.id)
    expected = _discovery(request)
    assert [(row.fragrance.id, row.score, row.taste_match) for row in actual] == [
        (row.fragrance.id, row.score, row.taste_match) for row in expected
    ]
    actual_pairs = LayeringService(LayeringRepository(session)).suggest(user.id)
    expected_pairs = _layering(request, "safe")
    assert [row.score for row in actual_pairs] == [row.score for row in expected_pairs]
