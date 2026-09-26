from __future__ import annotations

from decimal import Decimal

from domain_fixtures import make_brand, make_collection_item, make_fragrance, make_user
from sqlalchemy.orm import Session

from scentiq_api.models import Accord, Fragrance, FragranceAccord
from scentiq_api.repositories import DiscoveryRepository, FragranceRepository, LayeringRepository
from scentiq_api.schemas import FragranceCreateRequest
from scentiq_api.services import DiscoveryService, FragranceService, LayeringService


def test_catalog_summary_exposes_live_fields_and_top_three_accords(session: Session) -> None:
    user = make_user(session, email="summary@example.test")
    brand = make_brand(session, name="Source House")
    fragrance = make_fragrance(
        session,
        brand=brand,
        name="Source Scent",
        accords=("woody", "amber", "floral", "citrus"),
    )
    fragrance.gender = "unisex"
    fragrance.olfactory_family = "Woody"
    fragrance.image_url = "https://example.test/scent.jpg"
    fragrance.rating_average = Decimal("4.25")
    fragrance.rating_count = 42
    for index, link in enumerate(fragrance.accord_links):
        link.weight = Decimal("1.0") - Decimal(index) / Decimal("10")
    session.flush()

    result = FragranceService(FragranceRepository(session)).search(user.id)[0]

    assert result.gender == "unisex"
    assert result.olfactory_family == "Woody"
    assert result.image_url == "https://example.test/scent.jpg"
    assert result.rating_average == 4.25
    assert result.rating_count == 42
    assert len(result.top_accords) == 3


def test_catalog_search_filters_sorts_and_offsets(session: Session) -> None:
    user = make_user(session, email="filter@example.test")
    brand = make_brand(session, name="Filter House")
    low = make_fragrance(session, brand=brand, name="Low", seasons=("fall",))
    high = make_fragrance(session, brand=brand, name="High", seasons=("fall",))
    woody = Accord(name="Woody", slug="woody")
    session.add(woody)
    session.flush()
    for item in (low, high):
        session.add(FragranceAccord(fragrance_id=item.id, accord_id=woody.id, weight=Decimal("1")))
    for item, popularity in ((low, 10), (high, 100)):
        item.gender = "unisex"
        item.olfactory_family = "Woody"
        item.popularity_score = popularity
        item.search_text = f"filter house {item.name.lower()}"
    session.flush()

    result = FragranceService(FragranceRepository(session)).search(
        user.id,
        gender="unisex",
        family="Woody",
        season="fall",
        accord="woody",
        sort="popular",
        offset=1,
    )

    assert [item.name for item in result] == ["Low"]


def test_custom_fragrance_populates_folded_search_text(session: Session) -> None:
    user = make_user(session, email="custom-search@example.test")
    service = FragranceService(FragranceRepository(session))

    created = service.create_custom(
        user.id,
        FragranceCreateRequest(
            brand_name="Maison Élan", name="Crème & Cedar", concentration="Eau de Parfum"
        ),
    )

    stored = session.get(Fragrance, created.id)
    assert stored is not None
    assert stored.search_text == "maison elan creme and cedar eau de parfum"


def test_discovery_excludes_owned_and_returns_deterministic_scores(session: Session) -> None:
    user = make_user(session, email="discover@example.test")
    brand = make_brand(session, name="Discovery House")
    owned = make_fragrance(
        session,
        brand=brand,
        name="Owned",
        seasons=("fall",),
    )
    candidate = make_fragrance(
        session,
        brand=brand,
        name="Candidate",
        seasons=("fall",),
    )
    woody = Accord(name="Woody", slug="woody")
    amber = Accord(name="Amber", slug="amber")
    session.add_all((woody, amber))
    session.flush()
    session.add_all(
        (
            FragranceAccord(fragrance_id=owned.id, accord_id=woody.id, weight=Decimal("1")),
            FragranceAccord(fragrance_id=candidate.id, accord_id=woody.id, weight=Decimal("1")),
            FragranceAccord(fragrance_id=candidate.id, accord_id=amber.id, weight=Decimal("0.5")),
        )
    )
    candidate.popularity_score = 50
    make_collection_item(session, user=user, fragrance=owned)
    session.flush()

    results = DiscoveryService(DiscoveryRepository(session)).discover(user.id)

    assert [item.fragrance.id for item in results] == [candidate.id]
    assert results[0].taste_match > 0
    assert results[0].collection_expansion > 0
    assert 0 <= results[0].redundancy_risk <= 1


def test_layering_uses_owned_collection_and_is_deterministic(session: Session) -> None:
    user = make_user(session, email="layering@example.test")
    brand = make_brand(session, name="Layer House")
    first = make_fragrance(
        session,
        brand=brand,
        name="First",
        accords=("woody",),
        seasons=("fall",),
    )
    second = make_fragrance(
        session, brand=brand, name="Second", accords=("amber",), seasons=("fall",)
    )
    make_collection_item(session, user=user, fragrance=first)
    make_collection_item(session, user=user, fragrance=second)
    session.flush()

    results = LayeringService(LayeringRepository(session)).suggest(user.id, mode="safe")

    assert len(results) == 1
    assert {results[0].first.id, results[0].second.id} == {first.id, second.id}
    assert results[0].mode == "safe"
    assert results[0].season_overlap > 0
