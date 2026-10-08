import json
from collections import Counter
from pathlib import Path

import pytest

from scentiq_api.catalog_import.profile import (
    ProfileReport,
    SourceProfile,
    coverage,
    histogram_votes,
    is_meaningful,
    parse_olfactory_family,
    profile_sources,
    valid_year,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, False),
        ("", False),
        ("  ", False),
        ("NA", False),
        ("unknown", False),
        ([], False),
        ({}, False),
        ({"day": 0, "night": 0}, False),
        ({"day": 1, "night": 0}, True),
        ("Floral", True),
        (0, True),
    ],
)
def test_is_meaningful_rejects_placeholders_and_empty_vote_blocks(
    value: object, expected: bool
) -> None:
    assert is_meaningful(value) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1699, None),
        (1700, 1700),
        ("1989", 1989),
        (2100, 2100),
        (2101, None),
        ("unknown", None),
        (None, None),
    ],
)
def test_valid_year_clamps_to_supported_range(value: object, expected: int | None) -> None:
    assert valid_year(value) == expected


def test_histogram_votes_sums_counts_and_treats_missing_as_zero() -> None:
    assert histogram_votes([{"bucket": 1, "count": 2}, {"bucket": 2, "count": 3}]) == 5
    assert histogram_votes([]) == 0
    assert histogram_votes(None) == 0


def test_parse_olfactory_family_accepts_only_the_canonical_leading_phrase() -> None:
    assert (
        parse_olfactory_family("Orange Tonic by Azzaro is a Floral Green fragrance for women.")
        == "Floral Green"
    )
    assert (
        parse_olfactory_family(
            "Native is a fragrance for men. The maker calls it an ideal unisex fragrance for all."
        )
        is None
    )


def test_coverage_uses_meaningful_values_and_literal_percentage() -> None:
    result = coverage(["Floral", "NA", None, "Woody"], total=4)

    assert result.count == 2
    assert result.percent == 50.0


def test_profile_report_serializes_rejection_counters_as_string_keyed_objects() -> None:
    report = ProfileReport(
        inputs={},
        sources={
            "example": SourceProfile(
                rows_read=1,
                rows_rejected=1,
                rejection_reasons=Counter({"missing_identity": 1}),
            )
        },
        final_catalog_candidate_rows=0,
        inclusion_threshold_rows=0,
        excluded_attributes={},
    )

    payload = json.loads(json.dumps(report.to_dict()))

    assert payload["sources"]["example"]["rejection_reasons"] == {"missing_identity": 1}


def test_profile_sources_reads_all_five_logical_sources(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()

    # The archive/file contents are deliberately tiny; this test catches a
    # profiler that silently skips one of the two fra archive members.
    import csv
    import json
    import zipfile

    with zipfile.ZipFile(raw_dir / "fragrantica_full_kaggle.zip", "w") as archive:
        archive.writestr(
            "perfumes.jsonl",
            json.dumps(
                {
                    "id": 1,
                    "name": "Orange Tonic",
                    "brand": "Azzaro",
                    "year": None,
                    "gender": "female",
                    "description": "Orange Tonic by Azzaro is a Floral Green fragrance for women.",
                    "accords": [{"name": "citrus", "strength": 100}],
                    "notes": {"tiered": {"top": [{"name": "Orange", "weight": 100}]}, "flat": []},
                    "rating": {"average": 4.0, "histogram": [{"bucket": 4, "count": 5}]},
                    "seasons": {"summer": 5},
                    "daypart": {"day": 5, "night": 0},
                    "longevity": {"average": 3.0, "histogram": [{"bucket": 3, "count": 5}]},
                    "sillage": {"average": 2.0, "histogram": [{"bucket": 2, "count": 5}]},
                    "price_value": {"average": 4.0, "histogram": [{"bucket": 4, "count": 5}]},
                    "community_gender": {"female": 5},
                    "relation": {"have": 1, "had": 0, "want": 1},
                    "similar": {"reminds_me_of": [{"id": 2}], "also_liked": []},
                    "perfumers": [{"name": "Nathalie Feisthauer"}],
                    "collection": "TONIC",
                    "ai_summary": {"pros": [], "cons": []},
                    "popularity": {"magnitude": 3},
                }
            )
            + "\n"
            + json.dumps(
                {
                    "id": 2,
                    "name": "Unknown",
                    "brand": "Mith",
                    "gender": "unisex",
                    "relation": {"have": 0, "had": 0, "want": 0},
                    "popularity": {"magnitude": 0},
                }
            )
            + "\n",
        )

    with zipfile.ZipFile(raw_dir / "fragrantica_fra_perfumes.zip", "w") as archive:
        archive.writestr(
            "fra_cleaned.csv",
            "url;Perfume;Brand;Country;Gender;Rating Value;Rating Count;Year;"
            "Top;Middle;Base;Perfumer1;Perfumer2;mainaccord1;mainaccord2;"
            "mainaccord3;mainaccord4;mainaccord5\n"
            "https://example/orange-tonic-1.html;orange-tonic;azzaro;France;female;4,00;5;1999;Orange;;;;;citrus;;;;\n",
        )
        archive.writestr(
            "fra_perfumes.csv",
            "Name,Gender,Rating Value,Rating Count,Main Accords,Perfumers,Description,url\n"
            "Orange Tonic Azzaro,for women,4.0,5,\"['citrus']\",[],Text,https://example/orange-tonic-1.html\n",
        )

    parfumo = raw_dir / "parfumo_data_clean.csv"
    with parfumo.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "Number",
                "Name",
                "Brand",
                "Release_Year",
                "Concentration",
                "Rating_Value",
                "Rating_Count",
                "Main_Accords",
                "Top_Notes",
                "Middle_Notes",
                "Base_Notes",
                "Perfumers",
                "URL",
            ]
        )
        writer.writerow(
            [
                "1",
                "Orange Tonic",
                "Azzaro",
                "1999",
                "NA",
                "8",
                "5",
                "Citrus",
                "Orange",
                "NA",
                "NA",
                "Nathalie Feisthauer",
                "https://www.parfumo.com/Perfumes/Azzaro/orange-tonic",
            ]
        )

    with zipfile.ZipFile(raw_dir / "final_perfume_data.zip", "w") as archive:
        archive.writestr(
            "final_perfume_data.csv",
            "Name,Brand,Description,Notes,Image URL\nOrange Tonic Eau de Parfum,Azzaro,Editorial, Orange,https://example/image.jpg\n",
        )

    report = profile_sources(raw_dir)

    assert set(report.sources) == {
        "fragrantica",
        "fra_cleaned",
        "fra_perfumes",
        "parfumo",
        "luckyscent",
    }
    assert {name: source.rows_read for name, source in report.sources.items()} == {
        "fragrantica": 2,
        "fra_cleaned": 1,
        "fra_perfumes": 1,
        "parfumo": 1,
        "luckyscent": 1,
    }
    assert report.sources["fragrantica"].rows_rejected == 0
    assert report.sources["fragrantica"].coverage["official_gender"].count == 2
    assert report.sources["fragrantica"].coverage["relation_counts"].count == 1
    assert report.sources["fragrantica"].coverage["relation_counts"].percent == 50.0
    assert report.sources["fragrantica"].coverage["popularity_magnitude"].count == 1
    assert report.sources["fra_cleaned"].coverage["brand_country"].count == 1
    assert report.sources["luckyscent"].coverage["description"].count == 1
