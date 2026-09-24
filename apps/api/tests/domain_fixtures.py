"""Shared builders for domain tests.

These run against an in-memory SQLite database with foreign keys enforced, so
the ON DELETE CASCADE chain is genuinely exercised. Two things are PostgreSQL
specific and are covered by the integration tests instead: the partial unique
indexes (SQLite ignores `postgresql_where`, making them full unique indexes)
and `ilike` case-insensitivity on non-ASCII input.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from scentiq_api.models import (
    Accord,
    Brand,
    Fragrance,
    FragranceAccord,
    FragranceOccasion,
    FragranceSeason,
    User,
    UserCollectionItem,
    UserIdentity,
    WearLog,
)


def make_user(
    session: Session,
    *,
    email: str,
    subject: str | None = None,
    display_name: str = "Member",
) -> User:
    user = User(email=email, display_name=display_name, is_demo=False, lifecycle_state="active")
    session.add(user)
    session.flush()
    if subject is not None:
        session.add(UserIdentity(provider="clerk", subject=subject, user_id=user.id))
        session.flush()
    return user


def make_brand(session: Session, *, name: str, owner_user_id: UUID | None = None) -> Brand:
    brand = Brand(
        name=name,
        slug=name.lower().replace(" ", "-"),
        owner_user_id=owner_user_id,
    )
    session.add(brand)
    session.flush()
    return brand


def make_fragrance(
    session: Session,
    *,
    brand: Brand,
    name: str,
    concentration: str = "edp",
    owner_user_id: UUID | None = None,
    accords: tuple[str, ...] = (),
    seasons: tuple[str, ...] = (),
    occasions: tuple[str, ...] = (),
) -> Fragrance:
    fragrance = Fragrance(
        brand_id=brand.id,
        owner_user_id=owner_user_id,
        name=name,
        concentration=concentration,
    )
    session.add(fragrance)
    session.flush()

    for accord_name in accords:
        accord = Accord(
            name=f"{accord_name}-{uuid4().hex[:6]}", slug=f"{accord_name}-{uuid4().hex[:6]}"
        )
        session.add(accord)
        session.flush()
        session.add(
            FragranceAccord(
                fragrance_id=fragrance.id,
                accord_id=accord.id,
                weight=Decimal("0.50"),
            )
        )
    for season in seasons:
        session.add(
            FragranceSeason(
                fragrance_id=fragrance.id,
                season=season,
                weight=Decimal("0.80"),
            )
        )
    for occasion in occasions:
        session.add(
            FragranceOccasion(
                fragrance_id=fragrance.id,
                occasion=occasion,
                weight=Decimal("0.70"),
            )
        )
    session.flush()
    fragrance.brand = brand
    return fragrance


def make_collection_item(
    session: Session,
    *,
    user: User,
    fragrance: Fragrance,
    status: str = "owned",
    ownership_type: str = "bottle",
    purchase_price: str | None = None,
    user_rating: int | None = None,
) -> UserCollectionItem:
    item = UserCollectionItem(
        user_id=user.id,
        fragrance_id=fragrance.id,
        ownership_type=ownership_type,
        status=status,
        purchase_price=Decimal(purchase_price) if purchase_price is not None else None,
        user_rating=user_rating,
    )
    session.add(item)
    session.flush()
    item.fragrance = fragrance
    return item


def make_wear(
    session: Session,
    *,
    user: User,
    item: UserCollectionItem,
    days_ago: int = 1,
    notes: str | None = None,
) -> WearLog:
    entry = WearLog(
        user_id=user.id,
        collection_item_id=item.id,
        worn_at=datetime.now(UTC) - timedelta(days=days_ago),
        notes=notes,
    )
    session.add(entry)
    session.flush()
    return entry
