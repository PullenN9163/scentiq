from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import String, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.integration

API_ROOT = Path(__file__).parents[2]


def _alembic_config() -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    return config


def _reset_database() -> None:
    config = _alembic_config()
    command.downgrade(config, "base")
    command.upgrade(config, "head")


def test_catalog_import_migration_creates_postgresql_contract() -> None:
    _reset_database()
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        inspector = inspect(engine)
        assert {
            "catalog_import_runs",
            "fragrance_community_stats",
            "fragrance_perfumers",
            "fragrance_similarities",
            "fragrance_sources",
            "perfumers",
        } <= set(inspector.get_table_names())

        fragrance_columns = {
            column["name"]: column for column in inspector.get_columns("fragrances")
        }
        assert fragrance_columns["concentration"]["nullable"] is True
        fragrance_name_type = fragrance_columns["name"]["type"]
        assert isinstance(fragrance_name_type, String)
        assert fragrance_name_type.length == 255
        assert {
            "gender",
            "olfactory_family",
            "product_line",
            "image_url",
            "rating_average",
            "rating_count",
            "popularity_score",
            "search_text",
        } <= set(fragrance_columns)

        indexes = {index["name"]: index for index in inspector.get_indexes("fragrances")}
        assert (
            indexes["ix_fragrances_search_text_trgm"]["dialect_options"]["postgresql_using"]
            == "gin"
        )
        assert indexes["ix_fragrances_popularity_score_desc"]
        assert indexes["uq_fragrances_shared_identity"]["unique"] is True

        note_unique_constraints = inspector.get_unique_constraints("notes")
        assert not any(
            constraint["column_names"] == ["name"] for constraint in note_unique_constraints
        )

        with engine.connect() as connection:
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM pg_extension WHERE extname = 'pg_trgm'")
                )
                == 1
            )
    finally:
        engine.dispose()


def test_shared_identity_index_treats_nulls_as_equal() -> None:
    _reset_database()
    engine = create_engine(os.environ["DATABASE_URL"])
    brand_id = uuid4()
    try:
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO brands (id, name, slug) VALUES (:id, 'House', 'house')"),
                {"id": brand_id},
            )
            connection.execute(
                text(
                    "INSERT INTO fragrances "
                    "(id, brand_id, name, concentration, release_year, gender) "
                    "VALUES (:id, :brand, 'Scent', NULL, NULL, NULL)"
                ),
                {"id": uuid4(), "brand": brand_id},
            )
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO fragrances "
                    "(id, brand_id, name, concentration, release_year, gender) "
                    "VALUES (:id, :brand, 'Scent', NULL, NULL, NULL)"
                ),
                {"id": uuid4(), "brand": brand_id},
            )
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM fragrances WHERE brand_id = :brand"),
                {"brand": brand_id},
            )
            connection.execute(
                text("DELETE FROM brands WHERE id = :brand"),
                {"brand": brand_id},
            )
        engine.dispose()


def test_catalog_migration_downgrade_and_upgrade_are_reversible() -> None:
    _reset_database()
    config = _alembic_config()
    command.downgrade(config, "20260923_0003")

    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        inspector = inspect(engine)
        assert "fragrance_sources" not in inspector.get_table_names()
        columns = {column["name"]: column for column in inspector.get_columns("fragrances")}
        assert columns["concentration"]["nullable"] is False
        fragrance_name_type = columns["name"]["type"]
        assert isinstance(fragrance_name_type, String)
        assert fragrance_name_type.length == 160
        assert any(
            constraint["column_names"] == ["name"]
            for constraint in inspector.get_unique_constraints("notes")
        )
    finally:
        engine.dispose()

    command.upgrade(config, "head")
