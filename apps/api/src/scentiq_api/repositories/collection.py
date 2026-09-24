"""Collection access. Every method takes the authenticated user id and filters on it."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from scentiq_api.models import Fragrance, UserCollectionItem


class CollectionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(self, user_id: UUID) -> list[UserCollectionItem]:
        statement = (
            select(UserCollectionItem)
            .where(UserCollectionItem.user_id == user_id)
            .join(UserCollectionItem.fragrance)
            .options(
                joinedload(UserCollectionItem.fragrance).joinedload(Fragrance.brand),
            )
            .order_by(Fragrance.name)
        )
        return list(self._session.scalars(statement))

    def get_for_user(self, user_id: UUID, item_id: UUID) -> UserCollectionItem | None:
        """Ownership is part of the predicate, so another user's id yields None."""
        statement = (
            select(UserCollectionItem)
            .where(
                UserCollectionItem.id == item_id,
                UserCollectionItem.user_id == user_id,
            )
            .options(
                joinedload(UserCollectionItem.fragrance).joinedload(Fragrance.brand),
            )
        )
        return self._session.scalar(statement)

    def find_existing(self, user_id: UUID, fragrance_id: UUID) -> UserCollectionItem | None:
        statement = select(UserCollectionItem).where(
            UserCollectionItem.user_id == user_id,
            UserCollectionItem.fragrance_id == fragrance_id,
        )
        return self._session.scalar(statement)

    def add(self, item: UserCollectionItem) -> UserCollectionItem:
        self._session.add(item)
        self._session.flush()
        return item

    def apply_changes(
        self, item: UserCollectionItem, changes: dict[str, Any]
    ) -> UserCollectionItem:
        for field, value in changes.items():
            setattr(item, field, value)
        self._session.flush()
        return item
