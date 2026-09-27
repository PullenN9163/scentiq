"""Collection insights computed from persisted collection and wear history."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Row

from scentiq_api.repositories import InsightsRepository
from scentiq_api.schemas import (
    CollectionInsightsResponse,
    CountSlice,
    MostWornEntry,
    WeightedSlice,
)

RECENT_WINDOW = timedelta(days=30)


def _weighted(rows: list[Row[tuple[str, int]]]) -> list[WeightedSlice]:
    total = sum(count for _, count in rows)
    if total == 0:
        return []
    return [
        WeightedSlice(label=label, count=count, share=round(count / total, 3))
        for label, count in rows
    ]


class InsightsService:
    def __init__(self, repository: InsightsRepository) -> None:
        self._repository = repository

    def for_user(self, user_id: UUID, *, now: datetime | None = None) -> CollectionInsightsResponse:
        reference = now or datetime.now(UTC)
        since = reference - RECENT_WINDOW

        (
            total_items,
            owned_items,
            wishlist_items,
            retired_items,
            price_total,
            priced_items,
        ) = self._repository.collection_totals(user_id)
        average_rating, rated_items = self._repository.rating_summary(user_id)
        total_wears, recent_wears, distinct_worn = self._repository.wear_totals(user_id, since)

        return CollectionInsightsResponse(
            total_items=total_items,
            owned_items=owned_items,
            wishlist_items=wishlist_items,
            retired_items=retired_items,
            custom_items=self._repository.custom_item_count(user_id),
            # Null rather than "0.00" when nothing has a recorded price, so the
            # UI can distinguish "no data" from "free".
            total_purchase_value=(
                format(Decimal(price_total).quantize(Decimal("0.01")), "f")
                if price_total is not None
                else None
            ),
            priced_items=priced_items,
            average_rating=round(float(average_rating), 2) if average_rating is not None else None,
            rated_items=rated_items,
            total_wears=total_wears,
            wears_last_30_days=recent_wears,
            distinct_fragrances_worn=distinct_worn,
            most_worn=[
                MostWornEntry(
                    collection_item_id=item_id,
                    fragrance_id=fragrance_id,
                    fragrance_name=fragrance_name,
                    brand_name=brand_name,
                    wear_count=wear_count,
                )
                for item_id, fragrance_id, fragrance_name, brand_name, wear_count in (
                    self._repository.most_worn(user_id)
                )
            ],
            accords=_weighted(self._repository.accord_breakdown(user_id)),
            seasons=_weighted(self._repository.season_breakdown(user_id)),
            occasions=_weighted(self._repository.occasion_breakdown(user_id)),
            ownership_types=[
                CountSlice(label=label, count=count)
                for label, count in self._repository.ownership_type_counts(user_id)
            ],
            # Custom entries usually have no accords/seasons/occasions, so the
            # breakdowns above cover only part of the collection. Reporting the
            # remainder keeps the screen honest instead of implying full cover.
            unclassified_items=self._repository.unclassified_item_count(user_id),
        )
