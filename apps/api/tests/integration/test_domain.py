import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError

from scentiq_api.config import Settings
from scentiq_api.main import create_app
from scentiq_api.repositories import FragranceRepository

pytestmark = pytest.mark.integration

API_ROOT = Path(__file__).parents[2]
DEMO_USER_ID = "00000000-0000-4000-8000-000000000001"
AMBER_ATLAS_ID = "10000000-0000-4000-8000-000000000001"
REQUIRED_TABLES = {
    "accords",
    "brands",
    "calendar_events",
    "fragrance_accords",
    "fragrance_notes",
    "fragrance_occasions",
    "fragrance_seasons",
    "fragrances",
    "layering_logs",
    "notes",
    "recommendation_candidates",
    "recommendations",
    "user_collection",
    "user_preferences",
    "users",
    "wear_feedback",
    "wear_logs",
    "weather_snapshots",
    "wishlists",
}


def _alembic_config() -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    return config


def _reset_database() -> None:
    config = _alembic_config()
    command.downgrade(config, "base")
    command.upgrade(config, "head")


def _run_seed() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scentiq_api.seed"],
        cwd=API_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )


def _settings() -> Settings:
    return Settings(
        SCENTIQ_ENV="test",
        DATABASE_URL=os.environ["DATABASE_URL"],
        CORS_ORIGINS="http://localhost:5173",
    )


def _prepare_seeded_database() -> None:
    _reset_database()
    result = _run_seed()
    assert result.returncode == 0, result.stderr


def test_domain_migration_creates_exact_required_table_set() -> None:
    _reset_database()

    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        application_tables = set(inspect(engine).get_table_names()) - {"alembic_version"}
    finally:
        engine.dispose()

    assert application_tables == REQUIRED_TABLES


def test_seed_is_idempotent_and_reports_stable_counts() -> None:
    _reset_database()

    first = _run_seed()
    second = _run_seed()

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    expected = {
        "accords": 10,
        "brands": 3,
        "collection_items": 8,
        "fragrances": 15,
        "notes": 18,
        "users": 1,
    }
    assert json.loads(first.stdout) == expected
    assert json.loads(second.stdout) == expected


def test_fragrance_list_returns_seeded_catalog_in_stable_order() -> None:
    _prepare_seeded_database()

    with TestClient(create_app(_settings())) as client:
        response = client.get("/api/v1/fragrances")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 15
    assert payload[0] == {
        "brand": {
            "id": "01000000-0000-4000-8000-000000000001",
            "name": "ScentIQ Atelier",
            "slug": "scentiq-atelier",
        },
        "concentration": "eau_de_parfum",
        "id": AMBER_ATLAS_ID,
        "image_blob_path": None,
        "longevity_score": 8.2,
        "name": "Amber Atlas",
        "projection_level": "moderate",
        "release_year": 2026,
    }


def test_fragrance_detail_returns_nested_catalog_relationships() -> None:
    _prepare_seeded_database()

    with TestClient(create_app(_settings())) as client:
        response = client.get(f"/api/v1/fragrances/{AMBER_ATLAS_ID}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == AMBER_ATLAS_ID
    assert payload["name"] == "Amber Atlas"
    assert payload["description"] == "A warm amber study from the fictional ScentIQ demo catalog."
    assert payload["notes"] == [
        {
            "id": "02000000-0000-4000-8000-000000000001",
            "name": "Bergamot",
            "slug": "bergamot",
            "stage": "top",
        },
        {
            "id": "02000000-0000-4000-8000-000000000006",
            "name": "Labdanum",
            "slug": "labdanum",
            "stage": "middle",
        },
        {
            "id": "02000000-0000-4000-8000-000000000007",
            "name": "Vanilla",
            "slug": "vanilla",
            "stage": "base",
        },
    ]
    assert payload["accords"][0] == {
        "id": "03000000-0000-4000-8000-000000000001",
        "name": "Amber",
        "slug": "amber",
        "weight": 0.9,
    }
    assert payload["seasons"] == [
        {"season": "fall", "weight": 0.9},
        {"season": "winter", "weight": 1.0},
    ]
    assert payload["occasions"] == [
        {"occasion": "date", "weight": 0.8},
        {"occasion": "dinner", "weight": 0.9},
    ]


@pytest.mark.parametrize("fragrance_id", [str(UUID(int=0)), "not-a-uuid"])
def test_fragrance_detail_returns_stable_not_found_response(fragrance_id: str) -> None:
    _prepare_seeded_database()

    with TestClient(create_app(_settings())) as client:
        response = client.get(f"/api/v1/fragrances/{fragrance_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Fragrance not found"}


def test_collection_returns_only_the_configured_demo_users_items() -> None:
    _prepare_seeded_database()
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO users (id, email, display_name, is_demo, created_at, updated_at)
                    VALUES (
                        '00000000-0000-4000-8000-000000000099',
                        'other@example.invalid',
                        'Other User',
                        false,
                        now(),
                        now()
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO user_collection (
                        id, user_id, fragrance_id, ownership_type, status, created_at, updated_at
                    ) VALUES (
                        '40000000-0000-4000-8000-000000000099',
                        '00000000-0000-4000-8000-000000000099',
                        :fragrance_id,
                        'sample',
                        'owned',
                        now(),
                        now()
                    )
                    """
                ),
                {"fragrance_id": AMBER_ATLAS_ID},
            )
    finally:
        engine.dispose()

    with TestClient(create_app(_settings())) as client:
        response = client.get("/api/v1/collection")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 8
    assert {item["user_id"] for item in payload} == {DEMO_USER_ID}
    assert {item["ownership_type"] for item in payload} == {"bottle", "decant", "sample"}
    assert all(item["fragrance"]["name"] for item in payload)


def test_database_failures_return_a_sanitized_error(caplog: pytest.LogCaptureFixture) -> None:
    secret_marker = "postgresql://user:private-password@example.invalid/database"
    failure = OperationalError(
        "SELECT secret",
        {"password": secret_marker},
        Exception(secret_marker),
    )

    with (
        patch.object(FragranceRepository, "list", side_effect=failure),
        TestClient(create_app(_settings()), raise_server_exceptions=False) as client,
    ):
        response = client.get("/api/v1/fragrances")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert secret_marker not in caplog.text
