"""Collection insight contracts.

Insights are computed from persisted collection and wear history. Custom
fragrances often lack classification metadata, so every breakdown reports how
many items could not be classified rather than silently dropping them.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


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


class OwnedInsightEntry(MostWornEntry):
    last_worn_at: datetime | None
    user_rating: int | None
    cost_per_wear: str | None


class NoteFrequency(BaseModel):
    label: str
    stage: str
    count: int
    share: float


class RedundancyPair(BaseModel):
    first_id: UUID
    first_name: str
    second_id: UUID
    second_name: str
    overlap: float
    shared_accords: list[str]


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
    least_worn: list[OwnedInsightEntry] = Field(default_factory=list)
    neglected: list[OwnedInsightEntry] = Field(default_factory=list)
    highest_rated: list[OwnedInsightEntry] = Field(default_factory=list)
    cost_per_wear: list[OwnedInsightEntry] = Field(default_factory=list)
    note_frequency: list[NoteFrequency] = Field(default_factory=list)
    redundancy_pairs: list[RedundancyPair] = Field(default_factory=list)
    season_coverage_score: float | None = None
    season_evidence_coverage: float = 0
    season_gaps: list[str] = Field(default_factory=list)
    occasion_behavior: list[WeightedSlice] = Field(default_factory=list)
