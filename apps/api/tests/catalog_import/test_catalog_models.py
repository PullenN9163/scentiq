from decimal import Decimal

from sqlalchemy import CheckConstraint, Numeric, String, UniqueConstraint

from scentiq_api.models import Base, Fragrance, FragranceNote
from scentiq_api.schemas import FragranceSummary


def test_catalog_metadata_exposes_all_import_tables_and_columns() -> None:
    assert {
        "catalog_import_runs",
        "fragrance_community_stats",
        "fragrance_perfumers",
        "fragrance_similarities",
        "fragrance_sources",
        "perfumers",
    } <= set(Base.metadata.tables)

    brands = Base.metadata.tables["brands"]
    assert isinstance(brands.c.country.type, String)
    assert brands.c.country.type.length == 80
    assert brands.c.country.nullable is True

    fragrances = Base.metadata.tables["fragrances"]
    assert isinstance(fragrances.c.name.type, String)
    assert fragrances.c.name.type.length == 255
    assert fragrances.c.concentration.nullable is True
    assert {
        "gender",
        "olfactory_family",
        "product_line",
        "image_url",
        "rating_average",
        "rating_count",
        "popularity_score",
        "search_text",
    } <= set(fragrances.c.keys())

    fragrance_notes = Base.metadata.tables["fragrance_notes"]
    assert isinstance(fragrance_notes.c.weight.type, Numeric)
    assert fragrance_notes.c.weight.type.precision == 3
    assert fragrance_notes.c.weight.type.scale == 2
    checks = {
        str(constraint.sqltext)
        for constraint in fragrance_notes.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert "stage IN ('top', 'middle', 'base', 'general')" in checks

    notes = Base.metadata.tables["notes"]
    assert not any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == {"name"}
        for constraint in notes.constraints
    )


def test_catalog_model_checks_cover_import_ranges_and_identity() -> None:
    fragrances = Base.metadata.tables["fragrances"]
    checks = {
        str(constraint.sqltext)
        for constraint in fragrances.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert "gender IS NULL OR gender IN ('male', 'female', 'unisex')" in checks
    assert "rating_average IS NULL OR rating_average BETWEEN 0 AND 5" in checks
    assert "rating_count IS NULL OR rating_count >= 0" in checks
    assert "popularity_score IS NULL OR popularity_score >= 0" in checks

    sources = Base.metadata.tables["fragrance_sources"]
    source_record = next(
        constraint
        for constraint in sources.constraints
        if isinstance(constraint, UniqueConstraint) and constraint.name == "source_record"
    )
    assert {"source", "source_record_id"} == {column.name for column in source_record.columns}

    similarities = Base.metadata.tables["fragrance_similarities"]
    similarity_checks = {
        str(constraint.sqltext)
        for constraint in similarities.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert "fragrance_id <> similar_fragrance_id" in similarity_checks
    assert "kind IN ('reminds_me_of', 'also_liked')" in similarity_checks


def test_fragrance_summary_allows_unknown_concentration() -> None:
    response = FragranceSummary.model_validate(
        {
            "id": "10000000-0000-4000-8000-000000000001",
            "name": "Scent",
            "concentration": None,
            "release_year": None,
            "image_blob_path": None,
            "longevity_score": Decimal("7.0"),
            "projection_level": "moderate",
            "brand": {
                "id": "01000000-0000-4000-8000-000000000001",
                "name": "House",
                "slug": "house",
            },
        }
    )

    assert response.concentration is None


def test_general_note_stage_and_weight_are_constructible() -> None:
    link = FragranceNote(stage="general", weight=Decimal("0.75"))

    assert link.stage == "general"
    assert link.weight == Decimal("0.75")
    assert Fragrance.__table__.c.concentration.nullable is True
