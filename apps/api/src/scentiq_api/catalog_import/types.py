from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal

SourceName = Literal["fragrantica", "fra_cleaned", "fra_perfumes", "parfumo", "luckyscent"]
NoteStage = Literal["top", "middle", "base", "general"]
SimilarityKind = Literal["reminds_me_of", "also_liked"]


@dataclass(frozen=True)
class NoteValue:
    name: str
    key: str
    stage: NoteStage
    weight: Decimal | None = None


@dataclass(frozen=True)
class AccordValue:
    name: str
    key: str
    weight: Decimal


@dataclass(frozen=True)
class PerfumerValue:
    name: str
    key: str


@dataclass(frozen=True)
class SimilarityValue:
    source_record_id: str
    kind: SimilarityKind
    rank: int
    up_votes: int | None = None
    down_votes: int | None = None


@dataclass(frozen=True)
class CommunityValue:
    longevity_average: Decimal | None = None
    longevity_votes: int | None = None
    sillage_average: Decimal | None = None
    sillage_votes: int | None = None
    price_value_average: Decimal | None = None
    price_value_votes: int | None = None
    have_count: int | None = None
    had_count: int | None = None
    want_count: int | None = None
    perceived_female: int | None = None
    perceived_female_leaning: int | None = None
    perceived_unisex: int | None = None
    perceived_male_leaning: int | None = None
    perceived_male: int | None = None
    day_votes: int | None = None
    night_votes: int | None = None
    voters: int | None = None
    captured_at: datetime | None = None


@dataclass(frozen=True)
class SourceRecord:
    source: SourceName
    source_record_id: str
    source_url: str | None
    name: str | None
    brand: str | None
    brand_key: str | None
    name_key: str | None
    concentration: str | None = None
    release_year: int | None = None
    gender: str | None = None
    description: str | None = None
    country: str | None = None
    olfactory_family: str | None = None
    product_line: str | None = None
    image_url: str | None = None
    rating_average: Decimal | None = None
    rating_scale: Decimal | None = None
    rating_count: int | None = None
    popularity_score: int | None = None
    longevity_score: Decimal | None = None
    projection_level: str | None = None
    notes: tuple[NoteValue, ...] = ()
    accords: tuple[AccordValue, ...] = ()
    perfumers: tuple[PerfumerValue, ...] = ()
    seasons: dict[str, Decimal] = field(default_factory=dict)
    community: CommunityValue | None = None
    similarities: tuple[SimilarityValue, ...] = ()


@dataclass(frozen=True)
class RejectedRecord:
    source: SourceName
    row_number: int
    reason: str
    source_record_id: str | None = None
