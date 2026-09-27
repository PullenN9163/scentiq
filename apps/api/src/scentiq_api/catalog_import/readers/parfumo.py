from __future__ import annotations

import csv
from collections.abc import Iterator, Mapping
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

from scentiq_api.catalog_import.normalize import (
    brand_key,
    fold,
    meaningful_text,
    name_key,
    parse_decimal,
    parse_int,
    positional_weights,
    repair_mojibake,
    valid_year,
    year_hint,
)
from scentiq_api.catalog_import.types import (
    AccordValue,
    NoteStage,
    NoteValue,
    PerfumerValue,
    RejectedRecord,
    SourceRecord,
)


def _text(value: object) -> str | None:
    text = meaningful_text(value)
    return repair_mojibake(text) if text is not None else None


def _split(value: object) -> tuple[str, ...]:
    text = _text(value)
    return tuple(item.strip() for item in text.split(",") if item.strip()) if text else ()


def _source_id(url: str) -> str | None:
    marker = "/Perfumes/"
    path = urlparse(url).path
    if marker.casefold() not in path.casefold():
        return None
    index = path.casefold().index(marker.casefold()) + len(marker)
    return path[index:].strip("/") or None


def _notes(row: Mapping[str, str]) -> tuple[NoteValue, ...]:
    columns: tuple[tuple[NoteStage, str], ...] = (
        ("top", "Top_Notes"),
        ("middle", "Middle_Notes"),
        ("base", "Base_Notes"),
    )
    return tuple(
        NoteValue(name, fold(name), stage)
        for stage, column in columns
        for name in _split(row.get(column))
    )


def _perfumers(value: object) -> tuple[PerfumerValue, ...]:
    names = []
    for item in _split(value):
        latin_name = item.split(" / ", maxsplit=1)[0].strip()
        if latin_name and fold(latin_name) != "unknown":
            names.append(PerfumerValue(latin_name, fold(latin_name)))
    return tuple(names)


def _normalize(row: Mapping[str, str], row_number: int) -> SourceRecord | RejectedRecord:
    source_url = _text(row.get("URL"))
    source_id = _source_id(source_url) if source_url is not None else None
    name = _text(row.get("Name"))
    brand = _text(row.get("Brand"))
    if source_id is None or name is None or brand is None:
        return RejectedRecord("parfumo", row_number, "missing_identity", source_id)
    rating = parse_decimal(row.get("Rating_Value"))
    release_year = valid_year(row.get("Release_Year")) or year_hint(name)
    accords = tuple(
        AccordValue(accord, fold(accord), weight)
        for accord, weight in positional_weights(_split(row.get("Main_Accords")))
    )
    return SourceRecord(
        source="parfumo",
        source_record_id=source_id,
        source_url=source_url,
        name=name,
        brand=brand,
        brand_key=brand_key(brand),
        name_key=name_key(name, brand),
        concentration=_text(row.get("Concentration")),
        release_year=release_year,
        rating_average=rating,
        rating_scale=Decimal("10") if rating is not None else None,
        rating_count=parse_int(row.get("Rating_Count")),
        notes=_notes(row),
        accords=accords,
        perfumers=_perfumers(row.get("Perfumers")),
    )


def read_parfumo_file(path: Path) -> Iterator[SourceRecord | RejectedRecord]:
    with path.open(encoding="utf-8", newline="") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=2):
            yield _normalize(row, row_number)
