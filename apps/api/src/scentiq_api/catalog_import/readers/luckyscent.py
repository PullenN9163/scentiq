from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from collections.abc import Iterator, Mapping
from pathlib import Path

from scentiq_api.catalog_import.normalize import (
    brand_key,
    decode_luckyscent,
    fold,
    meaningful_text,
    name_key,
    parse_concentration,
)
from scentiq_api.catalog_import.types import NoteValue, RejectedRecord, SourceRecord


def _source_id(brand: str, name: str) -> str:
    return hashlib.sha1(f"{brand}|{name}".encode()).hexdigest()


def _notes(value: object) -> tuple[NoteValue, ...]:
    text = meaningful_text(value)
    if text is None:
        return ()
    names = (item.strip() for item in text.split(","))
    return tuple(NoteValue(name, fold(name), "general") for name in names if name)


def _normalize(row: Mapping[str, str], row_number: int) -> SourceRecord | RejectedRecord:
    name = meaningful_text(row.get("Name"))
    brand = meaningful_text(row.get("Brand"))
    if name is None or brand is None:
        return RejectedRecord("luckyscent", row_number, "missing_identity")
    return SourceRecord(
        source="luckyscent",
        source_record_id=_source_id(brand, name),
        source_url=None,
        name=name,
        brand=brand,
        brand_key=brand_key(brand),
        name_key=name_key(name, brand),
        concentration=parse_concentration(name),
        description=meaningful_text(row.get("Description")),
        image_url=meaningful_text(row.get("Image URL")),
        notes=_notes(row.get("Notes")),
    )


def read_luckyscent_archive(path: Path) -> Iterator[SourceRecord | RejectedRecord]:
    with zipfile.ZipFile(path) as archive:
        payload = archive.read("final_perfume_data.csv")
    reader = csv.DictReader(io.StringIO(decode_luckyscent(payload), newline=""))
    for row_number, row in enumerate(reader, start=2):
        yield _normalize(row, row_number)
