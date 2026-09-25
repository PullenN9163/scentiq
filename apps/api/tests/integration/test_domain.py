import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from auth_harness import auth_headers, resolver, settings
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from scentiq_api.config import Settings
from scentiq_api.main import create_app

pytestmark = pytest.mark.integration

API_ROOT = Path(__file__).parents[2]
DEMO_USER_ID = "00000000-0000-4000-8000-000000000001"
AMBER_ATLAS_ID = "10000000-0000-4000-8000-000000000001"
REQUIRED_TABLES = {
    "accords",
    "identity_events",
    "brands",
    "calendar_events",
    "catalog_import_runs",
    "fragrance_accords",
    "fragrance_community_stats",
    "fragrance_notes",
    "fragrance_occasions",
    "fragrance_perfumers",
    "fragrance_seasons",
    "fragrance_similarities",
    "fragrance_sources",
    "fragrances",
    "layering_logs",
    "notes",
    "perfumers",
    "recommendation_candidates",
    "recommendations",
    "user_collection",
    "user_identities",
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

    with TestClient(create_app(settings(), signing_key_resolver=resolver())) as client:
        response = client.get("/api/v1/fragrances", headers=auth_headers("user_catalog"))

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
        "is_custom": False,
        "longevity_score": 8.2,
        "name": "Amber Atlas",
        "projection_level": "moderate",
        "release_year": 2026,
    }


def test_fragrance_detail_returns_nested_catalog_relationships() -> None:
    _prepare_seeded_database()

    with TestClient(create_app(settings(), signing_key_resolver=resolver())) as client:
        response = client.get(
            f"/api/v1/fragrances/{AMBER_ATLAS_ID}",
            headers=auth_headers("user_detail"),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == AMBER_ATLAS_ID
    assert payload["name"] == "Amber Atlas"
    assert payload["is_custom"] is False
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


def test_unknown_fragrance_returns_the_standard_error_envelope() -> None:
    _prepare_seeded_database()

    with TestClient(create_app(settings(), signing_key_resolver=resolver())) as client:
        response = client.get(
            f"/api/v1/fragrances/{UUID(int=0)}",
            headers=auth_headers("user_missing"),
        )

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_malformed_fragrance_id_is_rejected_as_validation() -> None:
    _prepare_seeded_database()

    with TestClient(create_app(settings(), signing_key_resolver=resolver())) as client:
        response = client.get(
            "/api/v1/fragrances/not-a-uuid",
            headers=auth_headers("user_malformed"),
        )

    # The path parameter is a UUID, so this never reaches the service.
    assert response.status_code == 422
    assert response.json()["code"] == "unprocessable_entity"


def test_seeded_demo_collection_is_not_reachable_without_an_identity() -> None:
    """The demo user has no identity mapping, so no token can reach its data."""
    _prepare_seeded_database()

    with TestClient(create_app(settings(), signing_key_resolver=resolver())) as client:
        response = client.get("/api/v1/collection", headers=auth_headers("user_fresh"))

    assert response.status_code == 200
    # A newly provisioned user starts empty; the seeded demo rows stay invisible.
    assert response.json() == []
