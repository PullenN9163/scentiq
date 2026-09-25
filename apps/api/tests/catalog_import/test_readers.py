from __future__ import annotations

import zipfile
from decimal import Decimal
from pathlib import Path

from scentiq_api.catalog_import.readers import (
    read_fra_archive,
    read_fragrantica_archive,
    read_luckyscent_archive,
    read_parfumo_file,
)
from scentiq_api.catalog_import.types import RejectedRecord, SourceRecord

FIXTURES = Path(__file__).parents[1] / "fixtures" / "catalog_import"


def _zip_fixture(tmp_path: Path, archive_name: str, members: dict[str, tuple[Path, str]]) -> Path:
    archive_path = tmp_path / archive_name
    with zipfile.ZipFile(archive_path, "w") as archive:
        for member, (fixture, encoding) in members.items():
            archive.writestr(member, fixture.read_text(encoding="utf-8").encode(encoding))
    return archive_path


def test_fragrantica_reader_normalizes_all_supported_signal_groups(tmp_path: Path) -> None:
    archive = _zip_fixture(
        tmp_path,
        "fragrantica.zip",
        {"perfumes.jsonl": (FIXTURES / "fragrantica.jsonl", "utf-8")},
    )

    results = list(read_fragrantica_archive(archive))

    record = results[0]
    assert isinstance(record, SourceRecord)
    assert record.source_record_id == "1"
    assert record.name == "Orange Tonic Eau de Parfum"
    assert record.concentration == "Eau de Parfum"
    assert record.release_year == 2020
    assert record.olfactory_family == "Floral Green"
    assert record.rating_average == Decimal("4.2")
    assert record.rating_count == 5
    assert record.longevity_score == Decimal("5.0")
    assert record.projection_level == "moderate"
    assert record.notes[0].stage == "top"
    assert record.notes[0].key == "orange"
    assert record.notes[0].weight == Decimal("1")
    assert record.accords[1].weight == Decimal("0.4")
    assert record.seasons["fall"] == Decimal("0.75")
    assert record.similarities[0].source_record_id == "9"
    assert isinstance(results[1], RejectedRecord)
    assert results[1].reason == "missing_identity"


def test_fra_reader_uses_exact_ids_and_keeps_display_slugs_out_of_canonical_fields(
    tmp_path: Path,
) -> None:
    archive = _zip_fixture(
        tmp_path,
        "fra.zip",
        {
            "fra_cleaned.csv": (FIXTURES / "fra_cleaned.csv", "cp1252"),
            "fra_perfumes.csv": (FIXTURES / "fra_perfumes.csv", "utf-8"),
        },
    )

    results = list(read_fra_archive(archive))

    cleaned = results[0]
    fallback = results[1]
    assert isinstance(cleaned, SourceRecord)
    assert cleaned.source == "fra_cleaned"
    assert cleaned.source_record_id == "74630"
    assert cleaned.name is None
    assert cleaned.brand is None
    assert cleaned.country == "Italy"
    assert cleaned.rating_average == Decimal("1.42")
    assert [item.name for item in cleaned.perfumers] == []
    assert isinstance(fallback, SourceRecord)
    assert fallback.source == "fra_perfumes"
    assert fallback.source_record_id == "70706"
    assert fallback.name == "9am"
    assert fallback.brand == "Afnan"
    assert fallback.gender == "female"
    assert [item.name for item in fallback.perfumers] == ["Alice", "Bob"]


def test_parfumo_reader_repairs_text_and_keeps_latin_perfumer_name() -> None:
    results = list(read_parfumo_file(FIXTURES / "parfumo.csv"))

    record = results[0]
    assert isinstance(record, SourceRecord)
    assert record.source_record_id == "Le_Re_Noir/455-tabac-ecarlate"
    assert record.name == "Tabac Écarlate"
    assert record.brand == "Le Ré Noir"
    assert record.rating_average == Decimal("8.4")
    assert record.rating_scale == Decimal("10")
    assert record.concentration == "After Shave"
    assert [item.name for item in record.perfumers] == ["Valery Sokolov"]
    assert [item.stage for item in record.notes] == ["top", "top", "middle", "base"]


def test_luckyscent_reader_builds_stable_source_id_and_flat_notes(tmp_path: Path) -> None:
    archive = _zip_fixture(
        tmp_path,
        "luckyscent.zip",
        {"final_perfume_data.csv": (FIXTURES / "luckyscent.csv", "cp1252")},
    )

    results = list(read_luckyscent_archive(archive))

    record = results[0]
    assert isinstance(record, SourceRecord)
    assert record.source_record_id == "b4f5584b8a3874d42bb8a3a23ec221bc8f1b03be"
    assert record.concentration == "Eau de Parfum"
    assert record.description == "A real editorial description."
    assert [item.name for item in record.notes] == ["Vanilla bean", "musks"]
    assert all(item.stage == "general" for item in record.notes)
