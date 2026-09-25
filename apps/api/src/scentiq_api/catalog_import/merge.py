from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from scentiq_api.catalog_import.match import MatchResult, UnresolvedMatch, match_records
from scentiq_api.catalog_import.normalize import fold
from scentiq_api.catalog_import.types import (
    AccordValue,
    CommunityValue,
    NoteValue,
    PerfumerValue,
    SourceName,
    SourceRecord,
)


@dataclass(frozen=True)
class CanonicalSource:
    source: SourceName
    source_record_id: str
    source_url: str | None
    raw_name: str | None
    raw_brand: str | None
    rating_raw: Decimal | None
    rating_scale: Decimal | None
    rating_count: int | None
    field_origins: dict[str, str]


@dataclass(frozen=True)
class CanonicalSimilarity:
    similar_fragrance_id: UUID
    kind: str
    rank: int
    up_votes: int | None
    down_votes: int | None


@dataclass
class CanonicalFragrance:
    id: UUID
    primary_source: SourceName
    primary_source_record_id: str
    name: str
    brand: str
    brand_key: str
    country: str | None
    concentration: str | None
    release_year: int | None
    gender: str | None
    description: str | None
    olfactory_family: str | None
    product_line: str | None
    image_url: str | None
    rating_average: Decimal | None
    rating_count: int | None
    popularity_score: int | None
    longevity_score: Decimal | None
    projection_level: str | None
    notes: tuple[NoteValue, ...]
    accords: tuple[AccordValue, ...]
    perfumers: tuple[PerfumerValue, ...]
    seasons: dict[str, Decimal]
    community: CommunityValue | None
    sources: tuple[CanonicalSource, ...]
    field_origins: dict[str, str]
    similarities: tuple[CanonicalSimilarity, ...] = ()


@dataclass(frozen=True)
class CanonicalCatalog:
    fragrances: tuple[CanonicalFragrance, ...]
    unresolved: tuple[UnresolvedMatch, ...]
    rule_counts: dict[str, int]


def stable_catalog_id(source: str, source_record_id: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"scentiq:{source}:{source_record_id}")


def _rank(record: SourceRecord, priorities: Sequence[str]) -> tuple[int, int, str]:
    try:
        source_rank = priorities.index(record.source)
    except ValueError:
        source_rank = len(priorities)
    return source_rank, -(record.rating_count or 0), record.source_record_id


def _pick(
    records: Sequence[SourceRecord], field_name: str, priorities: Sequence[str]
) -> tuple[Any | None, SourceRecord | None]:
    for record in sorted(records, key=lambda item: _rank(item, priorities)):
        value = getattr(record, field_name)
        if value is not None and value != () and value != {}:
            return value, record
    return None, None


def _catalog_id(
    records: Sequence[SourceRecord],
    primary: SourceRecord,
    existing_sources: Mapping[tuple[str, str], UUID],
) -> UUID:
    existing = {
        existing_sources[(record.source, record.source_record_id)]
        for record in records
        if (record.source, record.source_record_id) in existing_sources
    }
    if len(existing) > 1:
        raise ValueError("conflicting existing canonical ids for matched source records")
    return (
        next(iter(existing))
        if existing
        else stable_catalog_id(primary.source, primary.source_record_id)
    )


def _rating(records: Sequence[SourceRecord]) -> tuple[Decimal | None, int | None]:
    weighted = Decimal("0")
    votes = 0
    for record in records:
        if (
            record.source not in {"fragrantica", "parfumo"}
            or record.rating_average is None
            or record.rating_scale is None
            or record.rating_scale <= 0
            or record.rating_count is None
            or record.rating_count <= 0
        ):
            continue
        normalized = record.rating_average * Decimal("5") / record.rating_scale
        weighted += normalized * record.rating_count
        votes += record.rating_count
    if votes == 0:
        return None, None
    return (
        (weighted / votes).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        votes,
    )


def _canonical_accords(
    accords: tuple[AccordValue, ...], aliases: Mapping[str, str]
) -> tuple[AccordValue, ...]:
    canonical_aliases = {fold(alias): fold(canonical) for alias, canonical in aliases.items()}
    result: list[AccordValue] = []
    seen: set[str] = set()
    for accord in accords:
        key = canonical_aliases.get(fold(accord.key), fold(accord.key))
        if key in seen:
            continue
        seen.add(key)
        name = accord.name if key == fold(accord.key) else key
        result.append(AccordValue(name, key, accord.weight))
    return tuple(result)


def _perfumers(records: Sequence[SourceRecord]) -> tuple[PerfumerValue, ...]:
    result: list[PerfumerValue] = []
    seen: set[str] = set()
    priorities = ("fragrantica", "fra_cleaned", "fra_perfumes", "parfumo", "luckyscent")
    for record in sorted(records, key=lambda item: _rank(item, priorities)):
        for perfumer in record.perfumers:
            if perfumer.key == "unknown" or perfumer.key in seen:
                continue
            seen.add(perfumer.key)
            result.append(perfumer)
    return tuple(result)


def _merge_group(
    match: MatchResult,
    group_index: int,
    existing_sources: Mapping[tuple[str, str], UUID],
    accord_aliases: Mapping[str, str],
) -> CanonicalFragrance:
    group = match.groups[group_index]
    records = group.records
    origins: dict[str, str] = {}
    origin_records: dict[str, SourceRecord] = {}

    def choose(field_name: str, priorities: Sequence[str]) -> Any | None:
        value, record = _pick(records, field_name, priorities)
        if record is not None:
            origins[field_name] = record.source
            origin_records[field_name] = record
        return value

    display_priority = ("fragrantica", "fra_perfumes", "parfumo", "luckyscent")
    name = choose("name", display_priority)
    brand = choose("brand", ("fragrantica", "fra_perfumes", "parfumo", "luckyscent"))
    if not isinstance(name, str) or not isinstance(brand, str):
        raise ValueError("canonical group has no display identity")

    concentration = choose("concentration", ("fragrantica", "parfumo", "luckyscent"))
    release_year = choose("release_year", ("fragrantica", "fra_cleaned", "parfumo"))
    gender = choose("gender", ("fragrantica", "fra_cleaned", "fra_perfumes"))
    description = choose("description", ("luckyscent", "fragrantica"))
    country = choose("country", ("fra_cleaned",))
    family = choose("olfactory_family", ("fragrantica",))
    product_line = choose("product_line", ("fragrantica",))
    image_url = choose("image_url", ("fragrantica", "luckyscent"))
    popularity = choose("popularity_score", ("fragrantica",))
    longevity = choose("longevity_score", ("fragrantica",))
    projection = choose("projection_level", ("fragrantica",))
    notes = choose("notes", ("fragrantica", "parfumo", "fra_cleaned", "luckyscent")) or ()
    accords = choose("accords", ("fragrantica", "fra_cleaned", "parfumo", "fra_perfumes")) or ()
    seasons = choose("seasons", ("fragrantica",)) or {}
    community = choose("community", ("fragrantica",))
    rating_average, rating_count = _rating(records)
    if rating_average is not None:
        origins["rating_average"] = "weighted:fragrantica+parfumo"
        origins["rating_count"] = "weighted:fragrantica+parfumo"

    per_source_fields: dict[tuple[str, str], dict[str, str]] = {
        (record.source, record.source_record_id): {} for record in records
    }
    for field_name, record in origin_records.items():
        per_source_fields[(record.source, record.source_record_id)][field_name] = "canonical"
    for record in records:
        if (
            record.source in {"fragrantica", "parfumo"}
            and record.rating_average is not None
            and record.rating_count is not None
            and record.rating_count > 0
        ):
            fields = per_source_fields[(record.source, record.source_record_id)]
            fields["rating_average"] = "weighted"
            fields["rating_count"] = "weighted"
    sources = tuple(
        CanonicalSource(
            source=record.source,
            source_record_id=record.source_record_id,
            source_url=record.source_url,
            raw_name=record.name,
            raw_brand=record.brand,
            rating_raw=record.rating_average,
            rating_scale=record.rating_scale,
            rating_count=record.rating_count,
            field_origins=per_source_fields[(record.source, record.source_record_id)],
        )
        for record in records
    )
    return CanonicalFragrance(
        id=_catalog_id(records, group.primary, existing_sources),
        primary_source=group.primary.source,
        primary_source_record_id=group.primary.source_record_id,
        name=name,
        brand=brand,
        brand_key=fold(brand),
        country=country,
        concentration=concentration,
        release_year=release_year,
        gender=gender,
        description=description,
        olfactory_family=family,
        product_line=product_line,
        image_url=image_url,
        rating_average=rating_average,
        rating_count=rating_count,
        popularity_score=popularity,
        longevity_score=longevity,
        projection_level=projection,
        notes=notes,
        accords=_canonical_accords(accords, accord_aliases),
        perfumers=_perfumers(records),
        seasons=seasons,
        community=community,
        sources=sources,
        field_origins=origins,
    )


def _resolve_similarities(
    fragrances: Sequence[CanonicalFragrance],
    groups: MatchResult,
) -> None:
    source_ids = {
        (record.source, record.source_record_id): fragrances[index].id
        for index, group in enumerate(groups.groups)
        for record in group.records
    }
    for index, group in enumerate(groups.groups):
        current = fragrances[index]
        resolved: list[CanonicalSimilarity] = []
        seen: set[tuple[UUID, str]] = set()
        for record in group.records:
            if record.source != "fragrantica":
                continue
            for similarity in record.similarities:
                target = source_ids.get(("fragrantica", similarity.source_record_id))
                key = (target, similarity.kind) if target is not None else None
                if target is None or target == current.id or key in seen:
                    continue
                seen.add((target, similarity.kind))
                resolved.append(
                    CanonicalSimilarity(
                        target,
                        similarity.kind,
                        similarity.rank,
                        similarity.up_votes,
                        similarity.down_votes,
                    )
                )
        current.similarities = tuple(resolved)


def build_canonical_catalog(
    records: Iterable[SourceRecord],
    brand_aliases: Mapping[str, str],
    existing_sources: Mapping[tuple[str, str], UUID],
    *,
    accord_aliases: Mapping[str, str] | None = None,
) -> CanonicalCatalog:
    match = match_records(records, brand_aliases)
    fragrances = tuple(
        _merge_group(match, index, existing_sources, accord_aliases or {})
        for index in range(len(match.groups))
    )
    _resolve_similarities(fragrances, match)
    return CanonicalCatalog(fragrances, match.unresolved, match.rule_counts)
