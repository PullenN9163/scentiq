from __future__ import annotations

import os
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from psycopg import Connection, sql

from scentiq_api.catalog_import.load import DEMO_BRAND_IDS, DEMO_FRAGRANCE_IDS, load_catalog
from scentiq_api.catalog_import.merge import CanonicalCatalog, build_canonical_catalog
from scentiq_api.catalog_import.types import (
    AccordValue,
    CommunityValue,
    NoteValue,
    PerfumerValue,
    SimilarityValue,
    SourceRecord,
)

pytestmark = pytest.mark.integration
API_ROOT = Path(__file__).parents[2]


def _database_url() -> str:
    return os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")


def _reset_database() -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    command.upgrade(config, "head")
    with psycopg.connect(_database_url()) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname='public' AND tablename <> 'alembic_version'"
        )
        tables = [sql.Identifier(row[0]) for row in cursor.fetchall()]
        if tables:
            cursor.execute(sql.SQL("TRUNCATE TABLE {} CASCADE").format(sql.SQL(",").join(tables)))


def _catalog(
    *, description: str = "First description", include_note: bool = True
) -> CanonicalCatalog:
    first = SourceRecord(
        source="fragrantica",
        source_record_id="10",
        source_url="https://example.test/10",
        name="First Scent",
        brand="Real House",
        brand_key="real house",
        name_key="first scent",
        concentration=None,
        release_year=2020,
        gender="unisex",
        description=description,
        olfactory_family="Woody",
        image_url="https://example.test/10.jpg",
        rating_average=Decimal("4.2"),
        rating_scale=Decimal("5"),
        rating_count=10,
        popularity_score=50,
        longevity_score=Decimal("7.5"),
        projection_level="moderate",
        notes=(NoteValue("Flowers", "floral notes", "general", Decimal("0.5")),)
        if include_note
        else (),
        accords=(AccordValue("Woody", "woody", Decimal("1")),),
        perfumers=(PerfumerValue("Nose One", "nose one"),),
        seasons={"fall": Decimal("1")},
        community=CommunityValue(longevity_average=Decimal("4"), longevity_votes=10),
        similarities=(SimilarityValue("11", "reminds_me_of", 1, 5, 1),),
    )
    second = replace(
        first,
        source_record_id="11",
        source_url="https://example.test/11",
        name="Second Scent",
        name_key="second scent",
        release_year=2021,
        description=None,
        notes=(),
        accords=(),
        perfumers=(),
        seasons={},
        community=None,
        similarities=(),
    )
    return build_canonical_catalog([first, second], {}, {})


def _insert_member_fixture(connection: Connection[tuple[object, ...]]) -> tuple[UUID, UUID]:
    user_id = uuid4()
    brand_id = uuid4()
    fragrance_id = uuid4()
    collection_id = uuid4()
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO users (id, email, display_name, is_demo) VALUES (%s, %s, %s, false)",
            (user_id, f"{user_id}@example.test", "Member"),
        )
        cursor.execute(
            "INSERT INTO brands (id, name, slug, owner_user_id) VALUES (%s, %s, %s, %s)",
            (brand_id, "Member House", f"member-{brand_id}", user_id),
        )
        cursor.execute(
            "INSERT INTO fragrances "
            "(id, brand_id, owner_user_id, name, concentration) VALUES (%s, %s, %s, %s, %s)",
            (fragrance_id, brand_id, user_id, "Member Scent", "Parfum"),
        )
        cursor.execute(
            "INSERT INTO user_collection "
            "(id, user_id, fragrance_id, ownership_type, status) "
            "VALUES (%s, %s, %s, 'bottle', 'owned')",
            (collection_id, user_id, fragrance_id),
        )
    connection.commit()
    return user_id, fragrance_id


def _member_snapshot(
    connection: Connection[tuple[object, ...]], user_id: UUID
) -> tuple[object, ...]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT "
            "(SELECT count(*) FROM brands WHERE owner_user_id = %s), "
            "(SELECT count(*) FROM fragrances WHERE owner_user_id = %s), "
            "(SELECT count(*) FROM user_collection WHERE user_id = %s), "
            "(SELECT md5(string_agg(to_jsonb(x)::text, '' ORDER BY id))) "
            " FROM (SELECT * FROM user_collection WHERE user_id = %s) x",
            (user_id, user_id, user_id, user_id),
        )
        row = cursor.fetchone()
    assert row is not None
    return row


def test_transactional_load_is_idempotent_and_preserves_member_data() -> None:
    _reset_database()
    with psycopg.connect(_database_url()) as connection:
        user_id, _ = _insert_member_fixture(connection)
        before = _member_snapshot(connection, user_id)

        first = load_catalog(connection, _catalog(), inputs={"fixture": {"sha256": "abc"}})
        after_first = _member_snapshot(connection, user_id)
        second = load_catalog(connection, _catalog(), inputs={"fixture": {"sha256": "abc"}})
        after_second = _member_snapshot(connection, user_id)

        assert first.counts["fragrances_inserted"] == 2
        assert first.catalog_changes > 0
        assert second.catalog_changes == 0
        assert before == after_first == after_second
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM fragrance_sources WHERE source = 'fragrantica'")
            assert cursor.fetchone() == (2,)
            cursor.execute("SELECT count(*) FROM fragrance_similarities")
            assert cursor.fetchone() == (1,)


def test_reload_replaces_imported_children_but_disappeared_fragrances_remain() -> None:
    _reset_database()
    with psycopg.connect(_database_url()) as connection:
        original = _catalog()
        load_catalog(connection, original, inputs={})
        changed = _catalog(description="Updated", include_note=False)

        result = load_catalog(connection, changed, inputs={})
        load_catalog(connection, CanonicalCatalog((), (), {}), inputs={})

        assert result.counts["fragrances_updated"] == 1
        assert result.counts["fragrance_notes_deleted"] == 1
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM fragrances WHERE owner_user_id IS NULL")
            assert cursor.fetchone() == (2,)
            cursor.execute("SELECT count(*) FROM fragrance_notes")
            assert cursor.fetchone() == (0,)


def test_demo_purge_deletes_only_unreferenced_shared_demo_rows() -> None:
    _reset_database()
    with psycopg.connect(_database_url()) as connection:
        user_id, member_fragrance_id = _insert_member_fixture(connection)
        before = _member_snapshot(connection, user_id)
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO brands (id, name, slug) VALUES (%s, 'Demo One', 'demo-one')",
                (DEMO_BRAND_IDS[0],),
            )
            cursor.execute(
                "INSERT INTO fragrances (id, brand_id, name, concentration) "
                "VALUES (%s, %s, 'Unreferenced Demo', 'edp'), (%s, %s, 'Referenced Demo', 'edp')",
                (
                    DEMO_FRAGRANCE_IDS[0],
                    DEMO_BRAND_IDS[0],
                    DEMO_FRAGRANCE_IDS[1],
                    DEMO_BRAND_IDS[0],
                ),
            )
            cursor.execute(
                "UPDATE user_collection SET fragrance_id = %s WHERE fragrance_id = %s",
                (DEMO_FRAGRANCE_IDS[1], member_fragrance_id),
            )
        connection.commit()
        before_purge = _member_snapshot(connection, user_id)

        result = load_catalog(
            connection,
            CanonicalCatalog((), (), {}),
            inputs={},
            purge_demo_catalog=True,
        )

        assert result.counts["demo_fragrances_deleted"] == 1
        assert result.counts["demo_fragrances_referenced"] == 1
        assert _member_snapshot(connection, user_id) == before_purge
        assert before != before_purge
