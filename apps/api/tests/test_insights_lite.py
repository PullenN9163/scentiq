from domain_fixtures import make_brand, make_collection_item, make_fragrance, make_user, make_wear
from sqlalchemy.orm import Session

from scentiq_api.repositories import InsightsRepository
from scentiq_api.services import InsightsService


def test_the_light_summary_agrees_with_the_full_report(session: Session) -> None:
    user = make_user(session, email="lite@example.test")
    brand = make_brand(session, name="Lite House")
    items = []
    for index in range(6):
        fragrance = make_fragrance(
            session,
            brand=brand,
            name=f"Lite {index}",
            accords=("woody", "fresh") if index % 2 else ("amber",),
            seasons=("fall",),
        )
        items.append(
            make_collection_item(
                session, user=user, fragrance=fragrance, purchase_price="50.00", user_rating=4
            )
        )
    make_wear(session, user=user, item=items[0], days_ago=3)
    session.flush()

    service = InsightsService(InsightsRepository(session))
    full = service.for_user(user.id)
    light = service.totals_for_user(user.id, with_accords=True)
    bare = service.totals_for_user(user.id)

    for field in (
        "total_items",
        "owned_items",
        "wishlist_items",
        "retired_items",
        "custom_items",
        "total_purchase_value",
        "priced_items",
        "average_rating",
        "rated_items",
        "total_wears",
        "wears_last_30_days",
        "distinct_fragrances_worn",
    ):
        assert getattr(light, field) == getattr(full, field), field
    assert light.accords == full.accords
    assert bare.accords == []
    assert light.most_worn == [] and light.redundancy_pairs == []
