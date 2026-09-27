from __future__ import annotations

import csv
import io
import re
import zipfile
from collections.abc import Iterator, Mapping
from decimal import Decimal
from pathlib import Path

from scentiq_api.catalog_import.normalize import (
    brand_key,
    fold,
    meaningful_text,
    name_key,
    normalize_gender,
    parse_decimal,
    parse_int,
    parse_python_list,
    positional_weights,
    valid_year,
)
from scentiq_api.catalog_import.types import (
    AccordValue,
    NoteStage,
    NoteValue,
    PerfumerValue,
    RejectedRecord,
    SourceRecord,
)

_ID = re.compile(r"-(\d+)\.html(?:$|[?#])", re.IGNORECASE)
_URL_BRAND = re.compile(r"/perfume/([^/]+)/", re.IGNORECASE)


def _source_id(url: object) -> str | None:
    match = _ID.search(str(url or ""))
    return match.group(1) if match else None


def _split(value: object) -> tuple[str, ...]:
    text = meaningful_text(value)
    return tuple(item.strip() for item in text.split(",") if item.strip()) if text else ()


def _notes(row: Mapping[str, str]) -> tuple[NoteValue, ...]:
    columns: tuple[tuple[NoteStage, str], ...] = (
        ("top", "Top"),
        ("middle", "Middle"),
        ("base", "Base"),
    )
    return tuple(
        NoteValue(name, fold(name), stage)
        for stage, column in columns
        for name in _split(row.get(column))
    )


def _accords(values: tuple[str, ...]) -> tuple[AccordValue, ...]:
    return tuple(
        AccordValue(name, fold(name), weight) for name, weight in positional_weights(values)
    )


def _cleaned(row: Mapping[str, str], row_number: int) -> SourceRecord | RejectedRecord:
    source_url = meaningful_text(row.get("url"))
    source_id = _source_id(source_url)
    if source_id is None:
        return RejectedRecord("fra_cleaned", row_number, "missing_identity")
    perfumer_names = tuple(
        value
        for key in ("Perfumer1", "Perfumer2")
        if (value := meaningful_text(row.get(key))) is not None and fold(value) != "unknown"
    )
    accord_names = tuple(
        value
        for index in range(1, 6)
        if (value := meaningful_text(row.get(f"mainaccord{index}"))) is not None
    )
    rating = parse_decimal(row.get("Rating Value"))
    return SourceRecord(
        source="fra_cleaned",
        source_record_id=source_id,
        source_url=source_url,
        name=None,
        brand=None,
        brand_key=None,
        name_key=None,
        release_year=valid_year(row.get("Year")),
        gender=normalize_gender(row.get("Gender")),
        country=meaningful_text(row.get("Country")),
        rating_average=rating,
        rating_scale=Decimal("5") if rating is not None else None,
        rating_count=parse_int(row.get("Rating Count")),
        notes=_notes(row),
        accords=_accords(accord_names),
        perfumers=tuple(PerfumerValue(name, fold(name)) for name in perfumer_names),
    )


def _fallback_display_name(raw_name: str, brand: str) -> str:
    result = re.sub(
        rf"\s*{re.escape(brand)}(?=for\b|\s|$)",
        " ",
        raw_name,
        flags=re.IGNORECASE,
    )
    result = re.sub(
        r"\s*for\s+(?:women\s+and\s+men|men\s+and\s+women|women|men)\s*$",
        "",
        result,
        flags=re.IGNORECASE,
    )
    return " ".join(result.split())


def _fallback(row: Mapping[str, str], row_number: int) -> SourceRecord | RejectedRecord:
    source_url = meaningful_text(row.get("url"))
    source_id = _source_id(source_url)
    raw_name = meaningful_text(row.get("Name"))
    if source_id is None or raw_name is None:
        return RejectedRecord("fra_perfumes", row_number, "missing_identity", source_id)
    brand_match = _URL_BRAND.search(source_url or "")
    brand = brand_match.group(1).replace("-", " ") if brand_match else None
    display_name = _fallback_display_name(raw_name, brand) if brand else raw_name
    display_name = display_name or raw_name
    perfumer_names = tuple(
        name for name in parse_python_list(row.get("Perfumers")) if fold(name) != "unknown"
    )
    rating = parse_decimal(row.get("Rating Value"))
    return SourceRecord(
        source="fra_perfumes",
        source_record_id=source_id,
        source_url=source_url,
        name=display_name,
        brand=brand,
        brand_key=brand_key(brand) if brand else None,
        name_key=name_key(display_name, brand),
        gender=normalize_gender(row.get("Gender")),
        rating_average=rating,
        rating_scale=Decimal("5") if rating is not None else None,
        rating_count=parse_int(row.get("Rating Count")),
        accords=_accords(parse_python_list(row.get("Main Accords"))),
        perfumers=tuple(PerfumerValue(name, fold(name)) for name in perfumer_names),
    )


def read_fra_archive(path: Path) -> Iterator[SourceRecord | RejectedRecord]:
    with zipfile.ZipFile(path) as archive:
        with archive.open("fra_cleaned.csv") as raw:
            reader = csv.DictReader(
                io.TextIOWrapper(raw, encoding="cp1252", newline=""), delimiter=";"
            )
            for row_number, row in enumerate(reader, start=2):
                yield _cleaned(row, row_number)
        with archive.open("fra_perfumes.csv") as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", newline=""))
            for row_number, row in enumerate(reader, start=2):
                yield _fallback(row, row_number)
