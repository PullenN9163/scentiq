from domain_fixtures import (
    make_brand,
    make_collection_item,
    make_fragrance,
    make_user,
    make_wear,
)
from sqlalchemy.orm import Session

from scentiq_api.repositories import DiscoveryRepository, InsightsRepository
from scentiq_api.services import DiscoveryService, InsightsService


def test_insights_cost_neglect_rating_and_evidence_are_member_scoped(session: Session) -> None:
    user = make_user(session, email="insights@example.test")
    other = make_user(session, email="insights-other@example.test")
    brand = make_brand(session, name="Insights House")
    fresh = make_fragrance(session, brand=brand, name="Fresh", seasons=("summer",))
    quiet = make_fragrance(session, brand=brand, name="Quiet")
    worn = make_collection_item(
        session, user=user, fragrance=fresh, purchase_price="100", user_rating=5
    )
    neglected = make_collection_item(session, user=user, fragrance=quiet, user_rating=3)
    make_collection_item(session, user=other, fragrance=quiet, purchase_price="999")
    make_wear(session, user=user, item=worn, days_ago=1)
    make_wear(session, user=user, item=worn, days_ago=2)
    result = InsightsService(InsightsRepository(session)).for_user(user.id)
    assert result.cost_per_wear[0].cost_per_wear == "50.00"
    assert result.neglected[0].collection_item_id == neglected.id
    assert result.highest_rated[0].collection_item_id == worn.id
    assert result.season_coverage_score == 0.2
    assert result.season_evidence_coverage == 0.5
    assert result.season_gaps == ["spring", "fall", "winter"]
    assert result.occasion_behavior == []


def test_discover_modes_materially_change_expansion_and_taste_ranking(session: Session) -> None:
    from decimal import Decimal

    from scentiq_api.models import Accord, FragranceAccord

    user = make_user(session, email="discover-mode@example.test")
    brand = make_brand(session, name="Discovery House")
    anchor = make_fragrance(session, brand=brand, name="Owned", seasons=("summer",))
    familiar = make_fragrance(session, brand=brand, name="Familiar", seasons=("summer",))
    novel = make_fragrance(session, brand=brand, name="Novel", seasons=("winter",))
    woody = Accord(name="Woody", slug="woody")
    amber = Accord(name="Amber", slug="amber")
    session.add_all([woody, amber])
    session.flush()
    for item, accord in ((anchor, woody), (familiar, woody), (novel, amber)):
        session.add(
            FragranceAccord(fragrance_id=item.id, accord_id=accord.id, weight=Decimal("0.8"))
        )
    make_collection_item(session, user=user, fragrance=anchor)
    session.flush()
    service = DiscoveryService(DiscoveryRepository(session))
    taste = service.discover(user.id, mode="taste")
    expansion = service.discover(user.id, mode="explore")
    assert taste[0].fragrance.id == familiar.id
    assert expansion[0].fragrance.id == novel.id
    seasonal = service.discover(user.id, mode="seasonal", season="summer")
    assert seasonal[0].fragrance.id == familiar.id
    assert seasonal[0].season_fit == 0.8
    assert seasonal[0].reasons


def test_discovery_loads_season_evidence_in_a_single_bounded_read(session: Session) -> None:
    from sqlalchemy import event

    user = make_user(session, email="discovery-query-count@example.test")
    user_id = user.id
    brand = make_brand(session, name="Discovery season queries")
    for index in range(10):
        make_fragrance(session, brand=brand, name=f"Catalog {index}", seasons=("summer",))
    session.flush()
    session.expunge_all()
    season_reads: list[str] = []

    def capture(
        connection: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: object,
    ) -> None:
        if statement.lstrip().startswith("SELECT") and "FROM fragrance_seasons" in statement:
            season_reads.append(statement)

    engine = session.get_bind()
    event.listen(engine, "before_cursor_execute", capture)
    try:
        result = DiscoveryService(DiscoveryRepository(session)).discover(user_id)
        assert len(result) == 10
        assert len(season_reads) == 1
    finally:
        event.remove(engine, "before_cursor_execute", capture)
