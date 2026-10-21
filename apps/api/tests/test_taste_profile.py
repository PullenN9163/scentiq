from domain_fixtures import make_brand, make_collection_item, make_fragrance, make_user
from sqlalchemy.orm import Session

from scentiq_api.models import UserPreference
from scentiq_api.schemas.identity import PreferencesUpdateRequest


def test_explicit_taste_is_normalized_and_rejects_conflicts() -> None:
    import pytest
    from pydantic import ValidationError

    request = PreferencesUpdateRequest(liked_accords=["  Fresh Spicy ", "fresh-spicy"])
    assert request.liked_accords == ["fresh-spicy"]
    with pytest.raises(ValidationError):
        PreferencesUpdateRequest(liked_accords=["woody"], disliked_accords=["Woody"])


def test_profile_learns_ratings_transfers_affinity_and_explicit_taste_wins(
    session: Session,
) -> None:
    from scentiq_api.services.taste_profile import TasteProfileService

    user = make_user(session, email="taste@example.test")
    brand = make_brand(session, name="Taste")
    loved = make_fragrance(session, brand=brand, name="Loved")
    loved.olfactory_family = "woody"
    similar = make_fragrance(session, brand=brand, name="Similar")
    similar.olfactory_family = "woody"
    neutral = make_fragrance(session, brand=brand, name="Neutral")
    neutral.olfactory_family = "citrus"
    make_collection_item(session, user=user, fragrance=loved, user_rating=5)
    profile = TasteProfileService(session).for_user(user.id)
    assert profile.affinity(similar) > profile.affinity(neutral)
    before = profile.version
    session.add(UserPreference(user_id=user.id, disliked_families=["woody"]))
    session.flush()
    explicit = TasteProfileService(session).for_user(user.id)
    assert explicit.version != before
    assert explicit.affinity(similar) < explicit.affinity(neutral)


def test_profile_deduplicates_bottles_and_isolates_members(session: Session) -> None:
    from scentiq_api.services.taste_profile import TasteProfileService

    user = make_user(session, email="taste-one@example.test")
    other = make_user(session, email="taste-two@example.test")
    fragrance = make_fragrance(session, brand=make_brand(session, name="Duplicates"), name="One")
    fragrance.olfactory_family = "floral"
    make_collection_item(session, user=user, fragrance=fragrance, user_rating=1)
    first = TasteProfileService(session).for_user(user.id)
    make_collection_item(
        session, user=user, fragrance=fragrance, ownership_type="decant", user_rating=1
    )
    assert TasteProfileService(session).for_user(user.id).affinity(fragrance) == first.affinity(
        fragrance
    )
    assert TasteProfileService(session).for_user(other.id).affinity(fragrance) == 0


def test_explicit_exclusion_is_available_to_every_surface(session: Session) -> None:
    from scentiq_api.services.taste_profile import TasteProfileService

    user = make_user(session, email="taste-exclusion@example.test")
    fragrance = make_fragrance(session, brand=make_brand(session, name="Excluded"), name="Excluded")
    session.add(UserPreference(user_id=user.id, excluded_fragrance_ids=[str(fragrance.id)]))
    session.flush()
    assert fragrance.id in TasteProfileService(session).for_user(user.id).excluded_ids
