from __future__ import annotations

import csv
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from rapidfuzz.fuzz import token_sort_ratio

from scentiq_api.catalog_import.normalize import fold
from scentiq_api.catalog_import.types import SourceRecord


@dataclass(frozen=True)
class MatchedGroup:
    primary: SourceRecord
    records: tuple[SourceRecord, ...]


@dataclass(frozen=True)
class UnresolvedMatch:
    record: SourceRecord
    candidate_source_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class MatchResult:
    groups: tuple[MatchedGroup, ...]
    unresolved: tuple[UnresolvedMatch, ...]
    rule_counts: dict[str, int]


@dataclass
class _Group:
    primary: SourceRecord
    records: list[SourceRecord] = field(default_factory=list)
    effective_concentration: str | None = None

    def __post_init__(self) -> None:
        if not self.records:
            self.records.append(self.primary)
        self.effective_concentration = self.primary.concentration

    def append(self, record: SourceRecord) -> None:
        self.records.append(record)
        if self.effective_concentration is None and record.concentration is not None:
            self.effective_concentration = record.concentration


def _source_sort_key(record: SourceRecord) -> tuple[int, int, str]:
    source_priority = {
        "fragrantica": 0,
        "fra_perfumes": 1,
        "parfumo": 2,
        "luckyscent": 3,
        "fra_cleaned": 4,
    }
    return (
        source_priority[record.source],
        -(record.rating_count or 0),
        record.source_record_id,
    )


def _brand(record: SourceRecord, aliases: Mapping[str, str]) -> str | None:
    if record.brand_key is None:
        return None
    key = fold(record.brand_key)
    return aliases.get(key, key)


def _compatible(record: SourceRecord, group: _Group) -> bool:
    concentration_matches = (
        record.concentration is None
        or group.effective_concentration is None
        or record.concentration == group.effective_concentration
    )
    year_matches = (
        record.release_year is None
        or group.primary.release_year is None
        or record.release_year == group.primary.release_year
    )
    return concentration_matches and year_matches


def _clear_popularity_winner(groups: list[_Group]) -> _Group | None:
    """Return a deliberately conservative winner for otherwise ambiguous matches.

    A lead is considered clear only when it is both at least 100 popularity points
    and two times the runner-up. Anything closer remains unresolved.
    """
    ranked = sorted(
        groups,
        key=lambda group: group.primary.popularity_score or 0,
        reverse=True,
    )
    if len(ranked) == 1:
        return ranked[0]
    first = ranked[0].primary.popularity_score or 0
    second = ranked[1].primary.popularity_score or 0
    return ranked[0] if first >= max(second * 2, second + 100) else None


def load_aliases_csv(path: Path) -> dict[str, str]:
    aliases: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["alias", "canonical"]:
            raise ValueError(f"alias file must have alias,canonical columns: {path}")
        for row in reader:
            alias = fold(row["alias"])
            canonical = fold(row["canonical"])
            if not alias or not canonical:
                raise ValueError(f"alias file contains a blank value: {path}")
            previous = aliases.setdefault(alias, canonical)
            if previous != canonical:
                raise ValueError(f"alias {alias!r} maps to multiple canonical values")
    return aliases


def _break_tie(record: SourceRecord, candidates: list[_Group]) -> _Group | None:
    remaining = candidates
    if record.release_year is not None:
        exact_year = [
            group for group in remaining if group.primary.release_year == record.release_year
        ]
        if exact_year:
            remaining = exact_year
    if len(remaining) == 1:
        return remaining[0]
    if record.concentration is not None:
        exact_concentration = [
            group for group in remaining if group.effective_concentration == record.concentration
        ]
        if exact_concentration:
            remaining = exact_concentration
    if len(remaining) == 1:
        return remaining[0]
    return _clear_popularity_winner(remaining)


def _find_match(
    record: SourceRecord,
    groups_by_brand: Mapping[str, list[_Group]],
    aliases: Mapping[str, str],
) -> tuple[_Group | None, list[_Group], str]:
    brand = _brand(record, aliases)
    if brand is None or record.name_key is None:
        return None, [], "missing_match_key"
    same_brand = groups_by_brand.get(brand, [])
    exact = [
        group
        for group in same_brand
        if group.primary.name_key == record.name_key and _compatible(record, group)
    ]
    if len(exact) == 1:
        return exact[0], exact, "exact_name"
    if len(exact) > 1:
        return _break_tie(record, exact), exact, "exact_name_tiebreak"

    fuzzy = [
        group
        for group in same_brand
        if group.primary.name_key is not None
        and _compatible(record, group)
        and token_sort_ratio(record.name_key, group.primary.name_key) >= 95
    ]
    if len(fuzzy) == 1:
        return fuzzy[0], fuzzy, "fuzzy_name"
    return None, fuzzy, "fuzzy_ambiguous" if fuzzy else "unmatched"


def match_records(records: Iterable[SourceRecord], brand_aliases: Mapping[str, str]) -> MatchResult:
    aliases = {fold(alias): fold(canonical) for alias, canonical in brand_aliases.items()}
    source_records: dict[tuple[str, str], SourceRecord] = {}
    counts: Counter[str] = Counter()
    for record in records:
        key = (record.source, record.source_record_id)
        if key in source_records:
            counts["duplicate_source_rows"] += 1
            continue
        source_records[key] = record

    fragrantica = sorted(
        (record for record in source_records.values() if record.source == "fragrantica"),
        key=_source_sort_key,
    )
    internal: dict[tuple[str | None, str | None, int | None, str | None], list[_Group]] = (
        defaultdict(list)
    )
    groups: list[_Group] = []
    id_groups: dict[str, _Group] = {}
    for record in fragrantica:
        identity = (
            _brand(record, aliases),
            record.name_key,
            record.release_year,
            record.gender,
        )
        candidates = [group for group in internal[identity] if _compatible(record, group)]
        target = candidates[0] if candidates else None
        if target is None:
            target = _Group(record)
            internal[identity].append(target)
            groups.append(target)
            counts["fragrantica_canonical"] += 1
        else:
            target.append(record)
            counts["fragrantica_internal_merge"] += 1
        id_groups[record.source_record_id] = target

    unmatched_fallbacks: list[SourceRecord] = []
    for source in ("fra_cleaned", "fra_perfumes"):
        for record in sorted(
            (item for item in source_records.values() if item.source == source),
            key=_source_sort_key,
        ):
            if target := id_groups.get(record.source_record_id):
                target.append(record)
                counts[f"{source}_id_join"] += 1
            elif source == "fra_perfumes" and record.name is not None and record.brand is not None:
                unmatched_fallbacks.append(record)
            else:
                counts[f"{source}_orphan"] += 1

    groups_by_brand: dict[str, list[_Group]] = defaultdict(list)
    for group in groups:
        if (brand := _brand(group.primary, aliases)) is not None:
            groups_by_brand[brand].append(group)

    cross_sources = (
        unmatched_fallbacks
        + sorted(
            (record for record in source_records.values() if record.source == "parfumo"),
            key=_source_sort_key,
        )
        + sorted(
            (record for record in source_records.values() if record.source == "luckyscent"),
            key=_source_sort_key,
        )
    )
    unresolved: list[UnresolvedMatch] = []
    for record in cross_sources:
        target, candidates, rule = _find_match(record, groups_by_brand, aliases)
        if target is not None:
            target.append(record)
            counts[f"{record.source}_{rule}"] += 1
            continue
        if candidates:
            unresolved.append(
                UnresolvedMatch(
                    record,
                    tuple(candidate.primary.source_record_id for candidate in candidates),
                    rule,
                )
            )
            counts[f"{record.source}_unresolved"] += 1
            continue
        target = _Group(record)
        groups.append(target)
        if (brand := _brand(record, aliases)) is not None:
            groups_by_brand[brand].append(target)
        counts[f"{record.source}_new"] += 1

    return MatchResult(
        groups=tuple(MatchedGroup(group.primary, tuple(group.records)) for group in groups),
        unresolved=tuple(unresolved),
        rule_counts=dict(counts),
    )
