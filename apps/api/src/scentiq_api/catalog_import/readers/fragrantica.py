from __future__ import annotations

import io
import json
import re
import zipfile
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from scentiq_api.catalog_import.normalize import (
    brand_key,
    fold,
    longevity_score,
    meaningful_text,
    name_key,
    normalize_gender,
    parse_concentration,
    parse_decimal,
    parse_int,
    projection_level,
    season_weights,
    valid_year,
)
from scentiq_api.catalog_import.types import (
    AccordValue,
    CommunityValue,
    NoteValue,
    PerfumerValue,
    RejectedRecord,
    SimilarityKind,
    SimilarityValue,
    SourceRecord,
)

_FAMILY = re.compile(r"\bis an? ([A-Z][A-Za-z-]+(?: [A-Z][A-Za-z-]+){0,3}) fragrance for\b")


def _identity_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _votes(value: object) -> int:
    if not isinstance(value, Mapping):
        return 0
    histogram = value.get("histogram")
    if not isinstance(histogram, list):
        return 0
    return sum(
        count
        for bucket in histogram
        if isinstance(bucket, Mapping)
        and (count := parse_int(bucket.get("count"))) is not None
        and count >= 0
    )


def _metric(value: object) -> tuple[Decimal | None, int]:
    if not isinstance(value, Mapping):
        return None, 0
    return parse_decimal(value.get("average")), _votes(value)


def _bounded_metric(
    value: object, minimum: Decimal, maximum: Decimal
) -> tuple[Decimal | None, int]:
    average, votes = _metric(value)
    if average is not None and not minimum <= average <= maximum:
        average = None
    return average, votes


def _mapping(value: object) -> Mapping[str, Any]:
    return cast(Mapping[str, Any], value) if isinstance(value, Mapping) else {}


def _notes(value: object) -> tuple[NoteValue, ...]:
    note_block = _mapping(value)
    tiered = _mapping(note_block.get("tiered"))
    result: list[NoteValue] = []
    if tiered:
        for stage in ("top", "middle", "base"):
            rows = tiered.get(stage)
            if not isinstance(rows, list):
                continue
            for row in rows:
                item = _mapping(row)
                name = meaningful_text(item.get("name"))
                if name is None:
                    continue
                slug = meaningful_text(item.get("slug")) or name
                raw_weight = parse_decimal(item.get("weight"))
                weight = raw_weight / Decimal("100") if raw_weight is not None else None
                result.append(NoteValue(name, fold(slug), stage, weight))
        if result:
            return tuple(result)
    flat = note_block.get("flat")
    if isinstance(flat, list):
        for row in flat:
            item = _mapping(row)
            name = meaningful_text(item.get("name"))
            if name is None:
                continue
            slug = meaningful_text(item.get("slug")) or name
            raw_weight = parse_decimal(item.get("weight"))
            weight = raw_weight / Decimal("100") if raw_weight is not None else None
            result.append(NoteValue(name, fold(slug), "general", weight))
    return tuple(result)


def _accords(value: object) -> tuple[AccordValue, ...]:
    if not isinstance(value, list):
        return ()
    result: list[AccordValue] = []
    for row in value:
        item = _mapping(row)
        name = meaningful_text(item.get("name"))
        strength = parse_decimal(item.get("strength"))
        if name is not None and strength is not None:
            result.append(AccordValue(name, fold(name), strength / Decimal("100")))
    return tuple(result)


def _perfumers(value: object) -> tuple[PerfumerValue, ...]:
    if not isinstance(value, list):
        return ()
    names = [meaningful_text(_mapping(item).get("name")) for item in value]
    return tuple(PerfumerValue(name, fold(name)) for name in names if name is not None)


def _similarities(value: object) -> tuple[SimilarityValue, ...]:
    block = _mapping(value)
    result: list[SimilarityValue] = []
    for source_key, kind in (
        ("reminds_me_of", "reminds_me_of"),
        ("also_liked", "also_liked"),
    ):
        rows = block.get(source_key)
        if not isinstance(rows, list):
            continue
        for rank, row in enumerate(rows, start=1):
            item = _mapping(row)
            target_id = parse_int(item.get("id"))
            if target_id is None:
                continue
            result.append(
                SimilarityValue(
                    str(target_id),
                    cast(SimilarityKind, kind),
                    rank,
                    parse_int(item.get("up_votes")),
                    parse_int(item.get("down_votes")),
                )
            )
    return tuple(result)


def _captured_at(value: object) -> datetime | None:
    seconds = parse_int(value)
    try:
        return datetime.fromtimestamp(seconds, tz=UTC) if seconds is not None else None
    except OSError, OverflowError, ValueError:
        return None


def _normalize(row: Mapping[str, Any], row_number: int) -> SourceRecord | RejectedRecord:
    record_id = parse_int(row.get("id"))
    name = _identity_text(row.get("name"))
    brand = _identity_text(row.get("brand"))
    if record_id is None or name is None or brand is None:
        return RejectedRecord(
            "fragrantica",
            row_number,
            "missing_identity",
            str(record_id) if record_id is not None else None,
        )

    rating_average, rating_count = _metric(row.get("rating"))
    longevity_average, longevity_votes = _bounded_metric(
        row.get("longevity"), Decimal("1"), Decimal("5")
    )
    sillage_average, sillage_votes = _bounded_metric(
        row.get("sillage"), Decimal("1"), Decimal("4")
    )
    price_average, price_votes = _bounded_metric(
        row.get("price_value"), Decimal("1"), Decimal("5")
    )
    relation = _mapping(row.get("relation"))
    perceived = _mapping(row.get("community_gender"))
    daypart = _mapping(row.get("daypart"))
    meta = _mapping(row.get("meta"))
    popularity = _mapping(row.get("popularity"))
    description = meaningful_text(row.get("description"))
    family_match = _FAMILY.search(description or "")

    return SourceRecord(
        source="fragrantica",
        source_record_id=str(record_id),
        source_url=meaningful_text(row.get("url")),
        name=name,
        brand=brand,
        brand_key=brand_key(brand),
        name_key=name_key(name, brand),
        concentration=parse_concentration(name),
        release_year=valid_year(row.get("year")),
        gender=normalize_gender(row.get("gender")),
        description=description,
        olfactory_family=family_match.group(1) if family_match else None,
        product_line=meaningful_text(row.get("collection")),
        image_url=f"https://fimgs.net/mdimg/perfume/375x500.{record_id}.jpg",
        rating_average=rating_average,
        rating_scale=Decimal("5") if rating_average is not None else None,
        rating_count=rating_count if rating_average is not None else None,
        popularity_score=parse_int(popularity.get("magnitude")),
        longevity_score=longevity_score(longevity_average, longevity_votes),
        projection_level=projection_level(sillage_average, sillage_votes),
        notes=_notes(row.get("notes")),
        accords=_accords(row.get("accords")),
        perfumers=_perfumers(row.get("perfumers")),
        seasons=season_weights(_mapping(row.get("seasons"))),
        community=CommunityValue(
            longevity_average=longevity_average,
            longevity_votes=longevity_votes or None,
            sillage_average=sillage_average,
            sillage_votes=sillage_votes or None,
            price_value_average=price_average,
            price_value_votes=price_votes or None,
            have_count=parse_int(relation.get("have")),
            had_count=parse_int(relation.get("had")),
            want_count=parse_int(relation.get("want")),
            perceived_female=parse_int(perceived.get("female")),
            perceived_female_leaning=parse_int(perceived.get("female_leaning")),
            perceived_unisex=parse_int(perceived.get("unisex")),
            perceived_male_leaning=parse_int(perceived.get("male_leaning")),
            perceived_male=parse_int(perceived.get("male")),
            day_votes=parse_int(daypart.get("day")),
            night_votes=parse_int(daypart.get("night")),
            voters=parse_int(row.get("people")),
            captured_at=_captured_at(meta.get("scraped_at")),
        ),
        similarities=_similarities(row.get("similar")),
    )


def read_fragrantica_archive(path: Path) -> Iterator[SourceRecord | RejectedRecord]:
    with zipfile.ZipFile(path) as archive, archive.open("perfumes.jsonl") as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8")
        for row_number, line in enumerate(text, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                yield RejectedRecord("fragrantica", row_number, "invalid_json")
                continue
            if not isinstance(row, dict):
                yield RejectedRecord("fragrantica", row_number, "invalid_record")
                continue
            yield _normalize(row, row_number)
