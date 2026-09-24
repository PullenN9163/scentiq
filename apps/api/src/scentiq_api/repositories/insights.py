"""Aggregate reads backing collection insights.

These are deliberately a handful of grouped queries rather than one wide join,
so a user with many wear logs does not multiply catalog rows.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Row, func, select
from sqlalchemy.orm import Session

from scentiq_api.models import (
    Accord,
    Brand,
    Fragrance,
    FragranceAccord,
    FragranceOccasion,
    FragranceSeason,
    UserCollectionItem,
    WearLog,
)


class InsightsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def collection_totals(
        self, user_id: UUID
    ) -> Row[tuple[int, int, int, int, Decimal | None, int]]:
        statement = select(
            func.count(UserCollectionItem.id),
            func.count(UserCollectionItem.id).filter(UserCollectionItem.status == "owned"),
            func.count(UserCollectionItem.id).filter(UserCollectionItem.status == "wishlist"),
            func.count(UserCollectionItem.id).filter(
                UserCollectionItem.status.in_(("finished", "sold"))
            ),
            func.sum(UserCollectionItem.purchase_price),
            func.count(UserCollectionItem.purchase_price),
        ).where(UserCollectionItem.user_id == user_id)
        return self._session.execute(statement).one()

    def rating_summary(self, user_id: UUID) -> Row[tuple[float | None, int]]:
        statement = select(
            func.avg(UserCollectionItem.user_rating),
            func.count(UserCollectionItem.user_rating),
        ).where(UserCollectionItem.user_id == user_id)
        return self._session.execute(statement).one()

    def custom_item_count(self, user_id: UUID) -> int:
        statement = (
            select(func.count(UserCollectionItem.id))
            .join(Fragrance, Fragrance.id == UserCollectionItem.fragrance_id)
            .where(
                UserCollectionItem.user_id == user_id,
                Fragrance.owner_user_id.is_not(None),
            )
        )
        return self._session.scalar(statement) or 0

    def ownership_type_counts(self, user_id: UUID) -> list[Row[tuple[str, int]]]:
        statement = (
            select(UserCollectionItem.ownership_type, func.count(UserCollectionItem.id))
            .where(UserCollectionItem.user_id == user_id)
            .group_by(UserCollectionItem.ownership_type)
            .order_by(func.count(UserCollectionItem.id).desc(), UserCollectionItem.ownership_type)
        )
        return list(self._session.execute(statement).all())

    def unclassified_item_count(self, user_id: UUID) -> int:
        """Items whose fragrance carries no accord, season or occasion rows.

        Custom entries normally land here, which is why insights report the
        number rather than pretending the breakdowns cover everything.
        """
        classified = (
            select(FragranceAccord.fragrance_id)
            .union(
                select(FragranceSeason.fragrance_id),
                select(FragranceOccasion.fragrance_id),
            )
            .subquery()
        )
        statement = select(func.count(UserCollectionItem.id)).where(
            UserCollectionItem.user_id == user_id,
            UserCollectionItem.fragrance_id.not_in(select(classified.c.fragrance_id)),
        )
        return self._session.scalar(statement) or 0

    def accord_breakdown(self, user_id: UUID) -> list[Row[tuple[str, int]]]:
        statement = (
            select(Accord.name, func.count(UserCollectionItem.id))
            .join(FragranceAccord, FragranceAccord.accord_id == Accord.id)
            .join(
                UserCollectionItem, UserCollectionItem.fragrance_id == FragranceAccord.fragrance_id
            )
            .where(UserCollectionItem.user_id == user_id)
            .group_by(Accord.name)
            .order_by(func.count(UserCollectionItem.id).desc(), Accord.name)
            .limit(12)
        )
        return list(self._session.execute(statement).all())

    def season_breakdown(self, user_id: UUID) -> list[Row[tuple[str, int]]]:
        statement = (
            select(FragranceSeason.season, func.count(UserCollectionItem.id))
            .join(
                UserCollectionItem,
                UserCollectionItem.fragrance_id == FragranceSeason.fragrance_id,
            )
            .where(UserCollectionItem.user_id == user_id)
            .group_by(FragranceSeason.season)
            .order_by(func.count(UserCollectionItem.id).desc(), FragranceSeason.season)
        )
        return list(self._session.execute(statement).all())

    def occasion_breakdown(self, user_id: UUID) -> list[Row[tuple[str, int]]]:
        statement = (
            select(FragranceOccasion.occasion, func.count(UserCollectionItem.id))
            .join(
                UserCollectionItem,
                UserCollectionItem.fragrance_id == FragranceOccasion.fragrance_id,
            )
            .where(UserCollectionItem.user_id == user_id)
            .group_by(FragranceOccasion.occasion)
            .order_by(func.count(UserCollectionItem.id).desc(), FragranceOccasion.occasion)
        )
        return list(self._session.execute(statement).all())

    def wear_totals(self, user_id: UUID, since: datetime) -> Row[tuple[int, int, int]]:
        statement = (
            select(
                func.count(WearLog.id),
                func.count(WearLog.id).filter(WearLog.worn_at >= since),
                func.count(func.distinct(UserCollectionItem.fragrance_id)),
            )
            .select_from(WearLog)
            .join(UserCollectionItem, UserCollectionItem.id == WearLog.collection_item_id)
            .where(WearLog.user_id == user_id)
        )
        return self._session.execute(statement).one()

    def most_worn(
        self, user_id: UUID, limit: int = 5
    ) -> list[Row[tuple[UUID, UUID, str, str, int]]]:
        statement = (
            select(
                UserCollectionItem.id,
                Fragrance.id,
                Fragrance.name,
                Brand.name,
                func.count(WearLog.id),
            )
            .select_from(WearLog)
            .join(UserCollectionItem, UserCollectionItem.id == WearLog.collection_item_id)
            .join(Fragrance, Fragrance.id == UserCollectionItem.fragrance_id)
            .join(Brand, Brand.id == Fragrance.brand_id)
            .where(WearLog.user_id == user_id)
            .group_by(UserCollectionItem.id, Fragrance.id, Fragrance.name, Brand.name)
            .order_by(func.count(WearLog.id).desc(), Fragrance.name)
            .limit(limit)
        )
        return list(self._session.execute(statement).all())
