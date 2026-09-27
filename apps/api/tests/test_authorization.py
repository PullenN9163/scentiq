"""Cross-user isolation.

Every one of these asserts that user B cannot see or change user A's data, and
that a private catalog entry is invisible rather than merely unwritable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from domain_fixtures import (
    make_brand,
    make_collection_item,
    make_fragrance,
    make_user,
    make_wear,
)
from sqlalchemy.orm import Session

from scentiq_api.errors import ApiError
from scentiq_api.repositories import (
    CollectionRepository,
    FragranceRepository,
    InsightsRepository,
    WearLogRepository,
)
from scentiq_api.schemas import (
    CollectionItemCreateRequest,
    CollectionItemUpdateRequest,
    WearLogCreateRequest,
)
from scentiq_api.services import (
    CollectionService,
    FragranceService,
    InsightsService,
    WearLogService,
)


def _collection_service(active: Session) -> CollectionService:
    return CollectionService(CollectionRepository(active), FragranceRepository(active))


def test_private_fragrance_is_invisible_to_other_users(session: Session) -> None:
    owner = make_user(session, email="owner@example.com", subject="user_owner")
    other = make_user(session, email="other@example.com", subject="user_other")
    brand = make_brand(session, name="Shared House")
    private = make_fragrance(
        session,
        brand=brand,
        name="Owner Private",
        owner_user_id=owner.id,
    )

    service = FragranceService(FragranceRepository(session))

    assert [item.id for item in service.search(owner.id)] == [private.id]
    assert service.search(other.id) == []


def test_private_fragrance_detail_is_not_found_for_other_user(session: Session) -> None:
    owner = make_user(session, email="owner@example.com")
    other = make_user(session, email="other@example.com")
    brand = make_brand(session, name="Shared House")
    private = make_fragrance(session, brand=brand, name="Private", owner_user_id=owner.id)

    service = FragranceService(FragranceRepository(session))

    # Not "forbidden": existence itself must not leak.
    with pytest.raises(ApiError) as error:
        service.get(other.id, private.id)
    assert error.value.status_code == 404


def test_shared_fragrance_is_visible_to_everyone(session: Session) -> None:
    first = make_user(session, email="first@example.com")
    second = make_user(session, email="second@example.com")
    brand = make_brand(session, name="Shared House")
    shared = make_fragrance(session, brand=brand, name="Curated", owner_user_id=None)

    service = FragranceService(FragranceRepository(session))

    assert [item.id for item in service.search(first.id)] == [shared.id]
    assert [item.id for item in service.search(second.id)] == [shared.id]
    assert service.get(second.id, shared.id).id == shared.id


def test_collection_list_is_scoped_to_owner(session: Session) -> None:
    owner = make_user(session, email="owner@example.com")
    other = make_user(session, email="other@example.com")
    brand = make_brand(session, name="Shared House")
    shared = make_fragrance(session, brand=brand, name="Curated")
    make_collection_item(session, user=owner, fragrance=shared)

    service = _collection_service(session)

    assert len(service.list_for_user(owner.id)) == 1
    assert service.list_for_user(other.id) == []


def test_collection_item_detail_is_not_found_for_other_user(session: Session) -> None:
    owner = make_user(session, email="owner@example.com")
    other = make_user(session, email="other@example.com")
    brand = make_brand(session, name="Shared House")
    shared = make_fragrance(session, brand=brand, name="Curated")
    item = make_collection_item(session, user=owner, fragrance=shared)

    service = _collection_service(session)

    with pytest.raises(ApiError) as error:
        service.get(other.id, item.id)
    assert error.value.status_code == 404


def test_other_user_cannot_update_collection_item(session: Session) -> None:
    owner = make_user(session, email="owner@example.com")
    other = make_user(session, email="other@example.com")
    brand = make_brand(session, name="Shared House")
    shared = make_fragrance(session, brand=brand, name="Curated")
    item = make_collection_item(session, user=owner, fragrance=shared, user_rating=5)

    service = _collection_service(session)

    with pytest.raises(ApiError) as error:
        service.update(other.id, item.id, CollectionItemUpdateRequest(user_rating=1))
    assert error.value.status_code == 404

    session.refresh(item)
    assert item.user_rating == 5


def test_cannot_add_another_users_private_fragrance_to_collection(session: Session) -> None:
    owner = make_user(session, email="owner@example.com")
    other = make_user(session, email="other@example.com")
    brand = make_brand(session, name="Shared House")
    private = make_fragrance(session, brand=brand, name="Private", owner_user_id=owner.id)

    service = _collection_service(session)

    with pytest.raises(ApiError) as error:
        service.add(
            other.id,
            CollectionItemCreateRequest(fragrance_id=private.id, ownership_type="bottle"),
        )
    assert error.value.status_code == 404


def test_wear_logs_are_scoped_to_owner(session: Session) -> None:
    owner = make_user(session, email="owner@example.com")
    other = make_user(session, email="other@example.com")
    brand = make_brand(session, name="Shared House")
    shared = make_fragrance(session, brand=brand, name="Curated")
    item = make_collection_item(session, user=owner, fragrance=shared)
    make_wear(session, user=owner, item=item)

    service = WearLogService(WearLogRepository(session), CollectionRepository(session))

    assert len(service.list_for_user(owner.id)) == 1
    assert service.list_for_user(other.id) == []


def test_cannot_log_wear_against_another_users_item(session: Session) -> None:
    owner = make_user(session, email="owner@example.com")
    other = make_user(session, email="other@example.com")
    brand = make_brand(session, name="Shared House")
    shared = make_fragrance(session, brand=brand, name="Curated")
    item = make_collection_item(session, user=owner, fragrance=shared)

    service = WearLogService(WearLogRepository(session), CollectionRepository(session))

    with pytest.raises(ApiError) as error:
        service.add(
            other.id,
            WearLogCreateRequest(
                collection_item_id=item.id,
                worn_at=datetime.now(UTC),
            ),
        )
    assert error.value.status_code == 404


def test_insights_only_count_the_callers_data(session: Session) -> None:
    owner = make_user(session, email="owner@example.com")
    other = make_user(session, email="other@example.com")
    brand = make_brand(session, name="Shared House")
    shared = make_fragrance(session, brand=brand, name="Curated")
    item = make_collection_item(session, user=owner, fragrance=shared, purchase_price="120.00")
    make_wear(session, user=owner, item=item)

    service = InsightsService(InsightsRepository(session))

    mine = service.for_user(owner.id)
    theirs = service.for_user(other.id)

    assert mine.total_items == 1
    assert mine.total_wears == 1
    assert mine.total_purchase_value == "120.00"

    assert theirs.total_items == 0
    assert theirs.total_wears == 0
    assert theirs.total_purchase_value is None


def test_unknown_ids_do_not_leak_existence(session: Session) -> None:
    user = make_user(session, email="user@example.com")
    service = _collection_service(session)

    with pytest.raises(ApiError) as error:
        service.get(user.id, uuid4())
    assert error.value.status_code == 404
