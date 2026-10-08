from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from scentiq_api.models import Fragrance, UserCollectionItem, UserPreference, WearLog
from scentiq_api.models.layer_stacks import LayerStack, LayerStackWear
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

    def collection_items(self, user_id: UUID) -> list[UserCollectionItem]:
        return list(
            self._session.scalars(
                select(UserCollectionItem).where(
                    UserCollectionItem.user_id == user_id, UserCollectionItem.status == "owned"
                )
            )
        )

    def preferences(self, user_id: UUID) -> UserPreference | None:
        return self._session.get(UserPreference, user_id)

    def wear_counts(self, user_id: UUID) -> dict[UUID, int]:
        rows = self._session.execute(
            select(UserCollectionItem.fragrance_id, func.count(WearLog.id))
            .join(WearLog, WearLog.collection_item_id == UserCollectionItem.id)
            .where(UserCollectionItem.user_id == user_id, WearLog.user_id == user_id)
            .group_by(UserCollectionItem.fragrance_id)
        ).all()
        return {fragrance_id: count for fragrance_id, count in rows}

    def stacks(self, user_id: UUID) -> list[LayerStack]:
        return list(
            self._session.scalars(
                select(LayerStack)
                .where(LayerStack.user_id == user_id)
                .options(selectinload(LayerStack.items), selectinload(LayerStack.wears))
                .order_by(LayerStack.created_at.desc(), LayerStack.id)
            )
        )

    def stack(self, user_id: UUID, stack_id: UUID) -> LayerStack | None:
        return self._session.scalar(
            select(LayerStack)
            .where(LayerStack.user_id == user_id, LayerStack.id == stack_id)
            .options(selectinload(LayerStack.items), selectinload(LayerStack.wears))
        )

    def stack_wear(self, user_id: UUID, stack_id: UUID, wear_id: UUID) -> LayerStackWear | None:
        return self._session.scalar(
            select(LayerStackWear).where(
                LayerStackWear.user_id == user_id,
                LayerStackWear.stack_id == stack_id,
                LayerStackWear.id == wear_id,
            )
        )

    def add(self, record: object) -> None:
        self._session.add(record)
        self._session.flush()

    def flush(self) -> None:
        self._session.flush()

    def delete(self, stack: LayerStack) -> None:
        self._session.delete(stack)
        self._session.flush()

    def commit(self) -> None:
        self._session.commit()
