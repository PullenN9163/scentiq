"""Wear-log access, always scoped to the authenticated user."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Row, select
from sqlalchemy.orm import Session

from scentiq_api.models import Brand, Fragrance, UserCollectionItem, WearLog

MAX_WEAR_LOG_LIMIT = 200

WearLogRow = Row[tuple[WearLog, UUID, str, str]]


class WearLogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(
        self,
        user_id: UUID,
        *,
        collection_item_id: UUID | None = None,
        fragrance_id: UUID | None = None,
        worn_from: datetime | None = None,
        worn_to: datetime | None = None,
        limit: int = 50,
    ) -> list[WearLogRow]:
        statement = (
            select(WearLog, Fragrance.id, Fragrance.name, Brand.name)
            .join(UserCollectionItem, UserCollectionItem.id == WearLog.collection_item_id)
            .join(Fragrance, Fragrance.id == UserCollectionItem.fragrance_id)
            .join(Brand, Brand.id == Fragrance.brand_id)
            .where(WearLog.user_id == user_id)
        )
        if collection_item_id is not None:
            statement = statement.where(WearLog.collection_item_id == collection_item_id)
        if fragrance_id is not None:
            statement = statement.where(UserCollectionItem.fragrance_id == fragrance_id)
        if worn_from is not None:
            statement = statement.where(WearLog.worn_at >= worn_from)
        if worn_to is not None:
            statement = statement.where(WearLog.worn_at <= worn_to)

        statement = statement.order_by(WearLog.worn_at.desc()).limit(
            min(max(limit, 1), MAX_WEAR_LOG_LIMIT)
        )
        return list(self._session.execute(statement).all())

    def add(self, entry: WearLog) -> WearLog:
        self._session.add(entry)
        self._session.flush()
        return entry
