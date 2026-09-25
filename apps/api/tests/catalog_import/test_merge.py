from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from scentiq_api.catalog_import.merge import build_canonical_catalog, stable_catalog_id
from scentiq_api.catalog_import.types import (
    AccordValue,
    NoteValue,
    PerfumerValue,
    SimilarityValue,
    SourceRecord,
)


def _record(source: str, source_id: str, **changes: Any) -> SourceRecord:
    base = SourceRecord(
        source=source,  # type: ignore[arg-type]
        source_record_id=source_id,
        source_url=f"https://example.test/{source_id}",
        name="Samsara",
        brand="Guerlain",
        brand_key="guerlain",
        name_key="samsara",
        concentration=None,
        release_year=None,
        gender=None,
    )
    return replace(base, **changes)


def test_stable_id_uses_primary_source_and_existing_source_mapping_wins() -> None:
    fragrantica = _record("fragrantica", "10")
    expected = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")

    generated = build_canonical_catalog([fragrantica], {}, {})
    existing = build_canonical_catalog([fragrantica], {}, {("fragrantica", "10"): expected})

    assert generated.fragrances[0].id == stable_catalog_id("fragrantica", "10")
    assert existing.fragrances[0].id == expected


def test_survivorship_and_weighted_rating_follow_source_precedence() -> None:
    fragrantica = _record(
        "fragrantica",
        "10",
        concentration="Eau de Parfum",
        release_year=1989,
        gender="female",
        description="Fragrantica description",
        olfactory_family="Amber Floral",
        product_line="Les Légendaires",
        image_url="https://img.test/f.jpg",
        rating_average=Decimal("4.0"),
        rating_scale=Decimal("5"),
        rating_count=100,
        popularity_score=500,
    )
    cleaned = _record("fra_cleaned", "10", name=None, brand=None, country="France")
    parfumo = _record(
        "parfumo",
        "guerlain/samsara",
        concentration=None,
        release_year=None,
        rating_average=Decimal("8.0"),
        rating_scale=Decimal("10"),
        rating_count=50,
    )
    luckyscent = _record(
        "luckyscent",
        "hash",
        description="Editorial description",
        image_url="https://img.test/l.jpg",
    )

    catalog = build_canonical_catalog([fragrantica, cleaned, parfumo, luckyscent], {}, {})
    item = catalog.fragrances[0]

    assert item.concentration == "Eau de Parfum"
    assert item.release_year == 1989
    assert item.gender == "female"
    assert item.description == "Editorial description"
    assert item.country == "France"
    assert item.image_url == "https://img.test/f.jpg"
    assert item.rating_average == Decimal("4.00")
    assert item.rating_count == 150
    assert item.field_origins["description"] == "luckyscent"


def test_children_use_one_source_while_perfumers_union_and_aliases_apply() -> None:
    fragrantica = _record(
        "fragrantica",
        "10",
        notes=(NoteValue("Flowers", "floral notes", "middle", Decimal("0.5")),),
        accords=(AccordValue("Woody", "woody", Decimal("0.9")),),
        perfumers=(PerfumerValue("Alice", "alice"),),
    )
    parfumo = _record(
        "parfumo",
        "guerlain/samsara",
        notes=(NoteValue("Rose", "rose", "middle"),),
        accords=(AccordValue("Leathery", "leathery", Decimal("1.0")),),
        perfumers=(PerfumerValue("Alice", "alice"), PerfumerValue("Bob", "bob")),
    )

    catalog = build_canonical_catalog(
        [fragrantica, parfumo], {}, {}, accord_aliases={"leathery": "leather"}
    )
    item = catalog.fragrances[0]

    assert [note.key for note in item.notes] == ["floral notes"]
    assert [accord.key for accord in item.accords] == ["woody"]
    assert [perfumer.name for perfumer in item.perfumers] == ["Alice", "Bob"]


def test_similarity_references_resolve_to_survivors_and_drop_self_or_missing() -> None:
    first = _record(
        "fragrantica",
        "10",
        name="First",
        name_key="first",
        similarities=(
            SimilarityValue("11", "reminds_me_of", 1, 5, 1),
            SimilarityValue("10", "reminds_me_of", 2, 3, 0),
            SimilarityValue("999", "also_liked", 3),
        ),
    )
    second = _record("fragrantica", "11", name="Second", name_key="second")

    catalog = build_canonical_catalog([first, second], {}, {})
    item = next(value for value in catalog.fragrances if value.name == "First")

    assert len(item.similarities) == 1
    assert item.similarities[0].similar_fragrance_id == stable_catalog_id("fragrantica", "11")


def test_conflicting_existing_source_ids_fail_closed() -> None:
    fragrantica = _record("fragrantica", "10")
    parfumo = _record("parfumo", "guerlain/samsara")

    with pytest.raises(ValueError, match="conflicting existing canonical ids"):
        build_canonical_catalog(
            [fragrantica, parfumo],
            {},
            {
                ("fragrantica", "10"): UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
                ("parfumo", "guerlain/samsara"): UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
            },
        )
