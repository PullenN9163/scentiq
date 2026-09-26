from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from scentiq_api.models import Fragrance, UserCollectionItem
from scentiq_api.repositories.fragrances import _catalog_options


class LayeringRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def owned(self, user_id: UUID) -> list[Fragrance]:
        statement = (
            select(Fragrance)
            .join(UserCollectionItem, UserCollectionItem.fragrance_id == Fragrance.id)
            .where(UserCollectionItem.user_id == user_id, UserCollectionItem.status == "owned")
            .options(*_catalog_options())
            .order_by(Fragrance.name, Fragrance.id)
        )
        return list(self._session.scalars(statement).unique())

    def owned_pair(self, user_id: UUID, fragrance_ids: set[UUID]) -> list[Fragrance]:
        statement = (
            select(Fragrance)
            .join(UserCollectionItem, UserCollectionItem.fragrance_id == Fragrance.id)
            .where(
                UserCollectionItem.user_id == user_id,
                UserCollectionItem.status == "owned",
                Fragrance.id.in_(fragrance_ids),
            )
            .options(*_catalog_options())
            .order_by(Fragrance.name, Fragrance.id)
        )
        return list(self._session.scalars(statement).unique())
