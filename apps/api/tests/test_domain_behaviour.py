"""Catalog search, custom-fragrance creation, collection lifecycle and insight maths."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from domain_fixtures import (
    make_brand,
    make_collection_item,
    make_fragrance,
    make_user,
    make_wear,
)
from pydantic import ValidationError
from sqlalchemy.orm import Session

from scentiq_api.errors import ApiError
from scentiq_api.repositories import (
    CollectionRepository,
    FragranceRepository,
    InsightsRepository,
    UserRepository,
    WearLogRepository,
)
from scentiq_api.schemas import (
    CollectionItemCreateRequest,
    CollectionItemUpdateRequest,
    FragranceCreateRequest,
    PreferencesUpdateRequest,
    WearLogCreateRequest,
)
from scentiq_api.services import (
    CollectionService,
    FragranceService,
    InsightsService,
    ProfileService,
    WearLogService,
)


def _collection(session: Session) -> CollectionService:
    return CollectionService(CollectionRepository(session), FragranceRepository(session))


# --- catalog search ----------------------------------------------------


def test_search_matches_fragrance_and_brand_name(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    brand = make_brand(session, name="Atelier Noir")
    make_fragrance(session, brand=brand, name="Vetiver Dusk")
    other_brand = make_brand(session, name="Botanica")
    make_fragrance(session, brand=other_brand, name="Fig Leaf")

    service = FragranceService(FragranceRepository(session))

    assert len(service.search(user.id, query="vetiver")) == 1
    # Brand name matches too.
    assert len(service.search(user.id, query="atelier")) == 1
    assert len(service.search(user.id, query="nothing here")) == 0


def test_search_is_case_insensitive(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    brand = make_brand(session, name="Atelier")
    make_fragrance(session, brand=brand, name="Vetiver Dusk")

    service = FragranceService(FragranceRepository(session))

    assert len(service.search(user.id, query="VETIVER")) == 1


def test_search_limit_is_capped(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    brand = make_brand(session, name="Atelier")
    for index in range(5):
        make_fragrance(session, brand=brand, name=f"Scent {index}")

    service = FragranceService(FragranceRepository(session))

    assert len(service.search(user.id, limit=2)) == 2


# --- custom fragrances -------------------------------------------------


def test_create_custom_fragrance_is_private_to_creator(session: Session) -> None:
    owner = make_user(session, email="owner@example.com")
    other = make_user(session, email="other@example.com")
    service = FragranceService(FragranceRepository(session))

    created = service.create_custom(
        owner.id,
        FragranceCreateRequest(brand_name="My House", name="My Scent", concentration="edp"),
    )
    session.commit()

    assert created.is_custom is True
    assert [item.id for item in service.search(owner.id)] == [created.id]
    assert service.search(other.id) == []


def test_custom_fragrance_reuses_a_shared_brand(session: Session) -> None:
    owner = make_user(session, email="owner@example.com")
    shared_brand = make_brand(session, name="Atelier Noir")
    service = FragranceService(FragranceRepository(session))

    created = service.create_custom(
        owner.id,
        FragranceCreateRequest(brand_name="atelier noir", name="Unlisted", concentration="edt"),
    )
    session.commit()

    # Matching a curated house avoids a private duplicate of it.
    assert created.brand.id == shared_brand.id


def test_duplicate_custom_fragrance_is_refused(session: Session) -> None:
    owner = make_user(session, email="owner@example.com")
    service = FragranceService(FragranceRepository(session))
    request = FragranceCreateRequest(brand_name="My House", name="My Scent", concentration="edp")
    service.create_custom(owner.id, request)
    session.commit()

    with pytest.raises(ApiError) as error:
        service.create_custom(owner.id, request)
    assert error.value.status_code == 409
    assert error.value.code == "fragrance_exists"


def test_custom_fragrance_requires_brand_name_and_concentration() -> None:
    with pytest.raises(ValidationError):
        FragranceCreateRequest(brand_name="  ", name="X", concentration="edp")
    with pytest.raises(ValidationError):
        FragranceCreateRequest(brand_name="House", name="  ", concentration="edp")
    with pytest.raises(ValidationError):
        FragranceCreateRequest(brand_name="House", name="X", concentration="  ")


def test_custom_fragrance_metadata_is_optional() -> None:
    request = FragranceCreateRequest(brand_name="House", name="X", concentration="edp")

    assert request.release_year is None
    assert request.description is None
    assert request.longevity_score is None
    assert request.projection_level is None


def test_custom_fragrance_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        FragranceCreateRequest.model_validate(
            {
                "brand_name": "House",
                "name": "X",
                "concentration": "edp",
                "owner_user_id": "00000000-0000-4000-8000-000000000001",
            }
        )


# --- collection lifecycle ----------------------------------------------


def test_add_collection_item_serialises_money_as_decimal_string(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    brand = make_brand(session, name="Atelier")
    fragrance = make_fragrance(session, brand=brand, name="Scent")
    service = _collection(session)

    created = service.add(
        user.id,
        CollectionItemCreateRequest(
            fragrance_id=fragrance.id,
            ownership_type="bottle",
            purchase_price=Decimal("129.5"),
        ),
    )

    assert created.purchase_price == "129.50"


def test_duplicate_collection_item_is_refused(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    brand = make_brand(session, name="Atelier")
    fragrance = make_fragrance(session, brand=brand, name="Scent")
    service = _collection(session)
    request = CollectionItemCreateRequest(fragrance_id=fragrance.id, ownership_type="bottle")
    service.add(user.id, request)

    with pytest.raises(ApiError) as error:
        service.add(user.id, request)
    assert error.value.code == "collection_item_exists"


def test_retiring_an_item_preserves_its_wear_history(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    brand = make_brand(session, name="Atelier")
    fragrance = make_fragrance(session, brand=brand, name="Scent")
    item = make_collection_item(session, user=user, fragrance=fragrance)
    make_wear(session, user=user, item=item)
    service = _collection(session)

    updated = service.update(user.id, item.id, CollectionItemUpdateRequest(status="finished"))

    assert updated.status == "finished"
    wear_service = WearLogService(WearLogRepository(session), CollectionRepository(session))
    assert len(wear_service.list_for_user(user.id)) == 1


def test_partial_update_leaves_omitted_fields_alone(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    brand = make_brand(session, name="Atelier")
    fragrance = make_fragrance(session, brand=brand, name="Scent")
    item = make_collection_item(
        session, user=user, fragrance=fragrance, purchase_price="100.00", user_rating=4
    )
    service = _collection(session)

    updated = service.update(user.id, item.id, CollectionItemUpdateRequest(user_rating=5))

    assert updated.user_rating == 5
    # Not mentioned, so untouched.
    assert updated.purchase_price == "100.00"


def test_explicit_null_clears_a_field(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    brand = make_brand(session, name="Atelier")
    fragrance = make_fragrance(session, brand=brand, name="Scent")
    item = make_collection_item(session, user=user, fragrance=fragrance, user_rating=4)
    service = _collection(session)

    updated = service.update(
        user.id,
        item.id,
        CollectionItemUpdateRequest.model_validate({"user_rating": None}),
    )

    assert updated.user_rating is None


def test_rating_outside_one_to_five_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CollectionItemUpdateRequest(user_rating=0)
    with pytest.raises(ValidationError):
        CollectionItemUpdateRequest(user_rating=6)


def test_collection_request_rejects_a_user_id_field() -> None:
    # Identity comes from the token; a caller-supplied user id must not validate.
    with pytest.raises(ValidationError):
        CollectionItemCreateRequest.model_validate(
            {
                "fragrance_id": "00000000-0000-4000-8000-000000000002",
                "ownership_type": "bottle",
                "user_id": "00000000-0000-4000-8000-000000000001",
            }
        )


# --- wear logs ---------------------------------------------------------


def test_wear_log_requires_a_timezone() -> None:
    with pytest.raises(ValidationError):
        WearLogCreateRequest(
            collection_item_id="00000000-0000-4000-8000-000000000002",
            worn_at=datetime(2026, 1, 1, 12, 0, 0),
        )


def test_wishlist_item_cannot_have_a_wear_logged(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    brand = make_brand(session, name="Atelier")
    fragrance = make_fragrance(session, brand=brand, name="Scent")
    item = make_collection_item(session, user=user, fragrance=fragrance, status="wishlist")
    service = WearLogService(WearLogRepository(session), CollectionRepository(session))

    with pytest.raises(ApiError) as error:
        service.add(
            user.id,
            WearLogCreateRequest(collection_item_id=item.id, worn_at=datetime.now(UTC)),
        )
    assert error.value.code == "item_not_wearable"


def test_wear_log_filters_by_date_range(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    brand = make_brand(session, name="Atelier")
    fragrance = make_fragrance(session, brand=brand, name="Scent")
    item = make_collection_item(session, user=user, fragrance=fragrance)
    make_wear(session, user=user, item=item, days_ago=1)
    make_wear(session, user=user, item=item, days_ago=40)
    service = WearLogService(WearLogRepository(session), CollectionRepository(session))

    recent = service.list_for_user(user.id, worn_from=datetime.now(UTC) - timedelta(days=7))

    assert len(recent) == 1


def test_wear_log_filters_by_fragrance(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    brand = make_brand(session, name="Atelier")
    first = make_fragrance(session, brand=brand, name="First")
    second = make_fragrance(session, brand=brand, name="Second")
    first_item = make_collection_item(session, user=user, fragrance=first)
    second_item = make_collection_item(session, user=user, fragrance=second)
    make_wear(session, user=user, item=first_item)
    make_wear(session, user=user, item=second_item)
    service = WearLogService(WearLogRepository(session), CollectionRepository(session))

    assert len(service.list_for_user(user.id, fragrance_id=first.id)) == 1


# --- insights ----------------------------------------------------------


def test_insights_on_an_empty_account_are_all_zero(session: Session) -> None:
    user = make_user(session, email="a@example.com")

    result = InsightsService(InsightsRepository(session)).for_user(user.id)

    assert result.total_items == 0
    assert result.total_purchase_value is None
    assert result.average_rating is None
    assert result.accords == []
    assert result.unclassified_items == 0


def test_insights_sum_money_and_average_ratings(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    brand = make_brand(session, name="Atelier")
    first = make_fragrance(session, brand=brand, name="First")
    second = make_fragrance(session, brand=brand, name="Second")
    make_collection_item(
        session, user=user, fragrance=first, purchase_price="100.00", user_rating=4
    )
    make_collection_item(
        session, user=user, fragrance=second, purchase_price="50.25", user_rating=5
    )

    result = InsightsService(InsightsRepository(session)).for_user(user.id)

    assert result.total_purchase_value == "150.25"
    assert result.priced_items == 2
    assert result.average_rating == 4.5
    assert result.rated_items == 2


def test_insights_count_statuses_separately(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    brand = make_brand(session, name="Atelier")
    for index, status in enumerate(("owned", "wishlist", "finished", "sold")):
        fragrance = make_fragrance(session, brand=brand, name=f"Scent {index}")
        make_collection_item(session, user=user, fragrance=fragrance, status=status)

    result = InsightsService(InsightsRepository(session)).for_user(user.id)

    assert result.total_items == 4
    assert result.owned_items == 1
    assert result.wishlist_items == 1
    assert result.retired_items == 2


def test_insights_report_items_with_no_classification(session: Session) -> None:
    """A custom entry with no accords/seasons/occasions is counted, not hidden."""
    user = make_user(session, email="a@example.com")
    brand = make_brand(session, name="Atelier")
    classified = make_fragrance(
        session,
        brand=brand,
        name="Curated",
        accords=("woody",),
        seasons=("winter",),
        occasions=("work",),
    )
    bare = make_fragrance(session, brand=brand, name="Bare Custom", owner_user_id=user.id)
    make_collection_item(session, user=user, fragrance=classified)
    make_collection_item(session, user=user, fragrance=bare)

    result = InsightsService(InsightsRepository(session)).for_user(user.id)

    assert result.total_items == 2
    assert result.custom_items == 1
    assert result.unclassified_items == 1
    # The breakdowns describe only the classified item.
    assert [slice_.label for slice_ in result.seasons] == ["winter"]
    assert result.seasons[0].count == 1


def test_insight_shares_sum_to_one(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    brand = make_brand(session, name="Atelier")
    first = make_fragrance(session, brand=brand, name="First", seasons=("winter",))
    second = make_fragrance(session, brand=brand, name="Second", seasons=("summer",))
    make_collection_item(session, user=user, fragrance=first)
    make_collection_item(session, user=user, fragrance=second)

    result = InsightsService(InsightsRepository(session)).for_user(user.id)

    assert round(sum(slice_.share for slice_ in result.seasons), 3) == 1.0


def test_insights_rank_most_worn(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    brand = make_brand(session, name="Atelier")
    favourite = make_fragrance(session, brand=brand, name="Favourite")
    rare = make_fragrance(session, brand=brand, name="Rare")
    favourite_item = make_collection_item(session, user=user, fragrance=favourite)
    rare_item = make_collection_item(session, user=user, fragrance=rare)
    for _ in range(3):
        make_wear(session, user=user, item=favourite_item)
    make_wear(session, user=user, item=rare_item)

    result = InsightsService(InsightsRepository(session)).for_user(user.id)

    assert result.total_wears == 4
    assert result.distinct_fragrances_worn == 2
    assert result.most_worn[0].fragrance_name == "Favourite"
    assert result.most_worn[0].wear_count == 3


def test_insights_recent_window_excludes_old_wears(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    brand = make_brand(session, name="Atelier")
    fragrance = make_fragrance(session, brand=brand, name="Scent")
    item = make_collection_item(session, user=user, fragrance=fragrance)
    make_wear(session, user=user, item=item, days_ago=2)
    make_wear(session, user=user, item=item, days_ago=90)

    result = InsightsService(InsightsRepository(session)).for_user(user.id)

    assert result.total_wears == 2
    assert result.wears_last_30_days == 1


# --- preferences -------------------------------------------------------


def test_preferences_round_trip(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    service = ProfileService(UserRepository(session))

    stored = service.replace_preferences(
        user.id,
        PreferencesUpdateRequest(
            location="Manchester",
            preferred_season="winter",
            preferred_projection="moderate",
            maximum_sprays=4,
        ),
    )

    assert stored.location == "Manchester"
    assert stored.preferred_season == "winter"
    assert stored.maximum_sprays == 4


def test_preferences_replace_clears_omitted_values(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    service = ProfileService(UserRepository(session))
    service.replace_preferences(user.id, PreferencesUpdateRequest(location="Manchester"))

    replaced = service.replace_preferences(user.id, PreferencesUpdateRequest())

    # A full replacement, so the previous location is cleared.
    assert replaced.location is None


def test_blank_location_is_stored_as_null() -> None:
    assert PreferencesUpdateRequest(location="   ").location is None


def test_preferences_reject_unknown_enum_values() -> None:
    with pytest.raises(ValidationError):
        PreferencesUpdateRequest(preferred_season="Winter")
    with pytest.raises(ValidationError):
        PreferencesUpdateRequest(maximum_sprays=99)
