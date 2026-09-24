"""Collection insight contracts.

Insights are computed from persisted collection and wear history. Custom
fragrances often lack classification metadata, so every breakdown reports how
many items could not be classified rather than silently dropping them.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class CountSlice(BaseModel):
    label: str
    count: int


class WeightedSlice(BaseModel):
    label: str
    count: int
    # Share of the classified total, 0..1, rounded to three decimals.
    share: float


class MostWornEntry(BaseModel):
    collection_item_id: UUID
    fragrance_id: UUID
    fragrance_name: str
    brand_name: str
    wear_count: int


class CollectionInsightsResponse(BaseModel):
    total_items: int
    owned_items: int
    wishlist_items: int
    retired_items: int
    custom_items: int
    # Money is serialised as a decimal string; null when nothing is priced.
    total_purchase_value: str | None
    priced_items: int
    average_rating: float | None
    rated_items: int
    total_wears: int
    wears_last_30_days: int
    distinct_fragrances_worn: int
    most_worn: list[MostWornEntry]
    accords: list[WeightedSlice]
    seasons: list[WeightedSlice]
    occasions: list[WeightedSlice]
    ownership_types: list[CountSlice]
    # Items with no shared-catalog classification to aggregate.
    unclassified_items: int
