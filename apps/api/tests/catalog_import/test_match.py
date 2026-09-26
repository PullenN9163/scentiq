from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from scentiq_api.catalog_import.match import load_aliases_csv, match_records
from scentiq_api.catalog_import.types import SourceRecord


def _record(
    source: str,
    source_id: str,
    *,
    name: str | None = "Samsara",
    brand: str | None = "Guerlain",
    year: int | None = 1989,
    gender: str | None = "female",
    concentration: str | None = "Eau de Parfum",
    rating_count: int | None = 100,
    popularity: int | None = 100,
) -> SourceRecord:
    return SourceRecord(
        source=source,  # type: ignore[arg-type]
        source_record_id=source_id,
        source_url=None,
        name=name,
        brand=brand,
        brand_key=brand.casefold() if brand else None,
        name_key=name.casefold() if name else None,
        release_year=year,
        gender=gender,
        concentration=concentration,
        rating_count=rating_count,
        popularity_score=popularity,
    )


def test_exact_fragrantica_id_sources_attach_to_the_same_group() -> None:
    fragrantica = _record("fragrantica", "10")
    cleaned = _record("fra_cleaned", "10", name=None, brand=None)
    fallback = _record("fra_perfumes", "10")

    result = match_records([fragrantica, cleaned, fallback], {})

    assert len(result.groups) == 1
    assert {record.source for record in result.groups[0].records} == {
        "fragrantica",
        "fra_cleaned",
        "fra_perfumes",
    }


def test_internal_duplicates_merge_but_distinct_reissues_remain_separate() -> None:
    survivor = _record("fragrantica", "10", rating_count=500)
    duplicate = replace(survivor, source_record_id="11", concentration=None, rating_count=10)
    reissue = replace(survivor, source_record_id="12", release_year=2021)
    different_gender = replace(survivor, source_record_id="13", gender="male")

    result = match_records([duplicate, reissue, survivor, different_gender], {})

    assert len(result.groups) == 3
    merged = next(group for group in result.groups if group.primary.source_record_id == "10")
    assert {record.source_record_id for record in merged.records} == {"10", "11"}


def test_cross_source_exact_match_accepts_unknown_concentration() -> None:
    fragrantica = _record("fragrantica", "10", concentration=None)
    parfumo = _record("parfumo", "guerlain/samsara", concentration="Eau de Parfum")

    result = match_records([fragrantica, parfumo], {})

    assert len(result.groups) == 1
    assert not result.unresolved


def test_multiple_compatible_candidates_use_exact_year_then_concentration() -> None:
    original = _record("fragrantica", "10", year=1989, concentration="Eau de Parfum")
    reissue = _record("fragrantica", "11", year=2021, concentration=None)
    parfumo = _record("parfumo", "guerlain/samsara", year=2021, concentration=None)

    result = match_records([original, reissue, parfumo], {})

    target = next(group for group in result.groups if group.primary.source_record_id == "11")
    assert {record.source for record in target.records} == {"fragrantica", "parfumo"}


def test_unclear_tie_is_unresolved_and_not_inserted() -> None:
    first = _record(
        "fragrantica", "10", year=None, gender="female", concentration=None, popularity=100
    )
    second = _record(
        "fragrantica", "11", year=None, gender="male", concentration=None, popularity=90
    )
    parfumo = _record("parfumo", "guerlain/samsara", year=None, concentration=None)

    result = match_records([first, second, parfumo], {})

    assert len(result.groups) == 2
    assert len(result.unresolved) == 1
    assert result.unresolved[0].record.source_record_id == "guerlain/samsara"
    assert set(result.unresolved[0].candidate_source_ids) == {"10", "11"}


def test_single_high_confidence_fuzzy_candidate_matches_within_brand() -> None:
    fragrantica = _record("fragrantica", "10", name="Orange Tonic", brand="Azzaro", year=None)
    parfumo = _record("parfumo", "azzaro/orange-tonic", name="Tonic Orange", year=None)
    parfumo = replace(parfumo, brand="Azzaro", brand_key="azzaro", name_key="tonic orange")

    result = match_records([fragrantica, parfumo], {})

    assert len(result.groups) == 1
    assert {record.source for record in result.groups[0].records} == {
        "fragrantica",
        "parfumo",
    }


def test_unmatched_cross_source_rows_deduplicate_once_and_brand_aliases_apply() -> None:
    parfumo = _record("parfumo", "ysl/opium", brand="YSL", year=1977)
    luckyscent = _record("luckyscent", "hash", brand="Yves Saint Laurent", year=None)

    result = match_records(
        [parfumo, luckyscent],
        {"ysl": "yves saint laurent"},
    )

    assert len(result.groups) == 1
    assert len(result.groups[0].records) == 2
    assert not result.unresolved


def test_alias_csv_loader_folds_values_and_rejects_conflicts(tmp_path: Path) -> None:
    path = tmp_path / "aliases.csv"
    path.write_text(
        "alias,canonical\nD.S. & Durga,DS&Durga\n",
        encoding="utf-8",
    )
    assert load_aliases_csv(path) == {"d s and durga": "ds and durga"}

    path.write_text("alias,canonical\nA,B\nA,C\n", encoding="utf-8")
    with pytest.raises(ValueError, match="multiple canonical"):
        load_aliases_csv(path)


def test_fra_cleaned_orphan_attaches_to_fra_perfumes_fallback_by_id() -> None:
    cleaned = _record(
        "fra_cleaned",
        "36536",
        name=None,
        brand=None,
        year=2012,
    )
    cleaned = replace(cleaned, country="France")
    fallback = _record(
        "fra_perfumes",
        "36536",
        name="Fallback Scent",
        brand="Fallback House",
        year=2012,
    )

    result = match_records([cleaned, fallback], {})

    assert len(result.groups) == 1
    assert {record.source for record in result.groups[0].records} == {
        "fra_cleaned",
        "fra_perfumes",
    }
    assert result.rule_counts["fra_cleaned_fallback_id_join"] == 1
