"""PostgreSQL-backed tests for identity, ownership and the authenticated contract.

These cover what SQLite cannot express: the partial unique indexes that make
shared catalog rows globally unique while custom rows are unique per owner, and
the ON DELETE CASCADE chain as PostgreSQL actually enforces it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from auth_harness import (
    SERVICE_TOKEN,
    auth_headers,
    resolver,
    settings,
    token,
    unconfigured_settings,
)
from catalog_fixture import load_test_catalog
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from scentiq_api.main import create_app

pytestmark = pytest.mark.integration

API_ROOT = Path(__file__).parents[2]
AMBER_ATLAS_ID = "10000000-0000-4000-8000-000000000001"


def _alembic_config() -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    return config


def _reset_database() -> None:
    config = _alembic_config()
    command.downgrade(config, "base")
    command.upgrade(config, "head")


def _seed() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "scentiq_api.seed"],
        cwd=API_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    assert result.returncode == 0, result.stderr


@pytest.fixture
def seeded() -> None:
    _reset_database()
    load_test_catalog()
    _seed()


@pytest.fixture
def client(seeded: None) -> TestClient:
    return TestClient(create_app(settings(), signing_key_resolver=resolver()))


# --- migrations ---------------------------------------------------------


def test_identity_tables_are_created() -> None:
    _reset_database()

    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert {"user_identities", "identity_events"} <= tables


def test_downgrade_then_upgrade_is_clean() -> None:
    config = _alembic_config()
    command.upgrade(config, "head")
    command.downgrade(config, "68bfbd3cf8fb")

    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        tables = set(inspect(engine).get_table_names())
        assert "user_identities" not in tables
        assert "identity_events" not in tables
    finally:
        engine.dispose()

    command.upgrade(config, "head")

    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        tables = set(inspect(engine).get_table_names())
        assert {"user_identities", "identity_events"} <= tables
    finally:
        engine.dispose()


def test_user_scoped_foreign_keys_cascade_on_delete() -> None:
    """Every user-scoped foreign key must carry ON DELETE CASCADE."""
    _reset_database()

    expected = {
        ("user_collection", "user_id"),
        ("user_collection", "fragrance_id"),
        ("wear_logs", "user_id"),
        ("wear_logs", "collection_item_id"),
        ("wear_feedback", "user_id"),
        ("wear_feedback", "wear_log_id"),
        ("wishlists", "user_id"),
        ("wishlists", "fragrance_id"),
        ("calendar_events", "user_id"),
        ("weather_snapshots", "user_id"),
        ("recommendations", "user_id"),
        ("user_identities", "user_id"),
        ("brands", "owner_user_id"),
        ("fragrances", "owner_user_id"),
    }

    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT tc.table_name, kcu.column_name, rc.delete_rule
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name
                    JOIN information_schema.referential_constraints rc
                      ON tc.constraint_name = rc.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                    """
                )
            ).all()
    finally:
        engine.dispose()

    rules = {(table, column): rule for table, column, rule in rows}
    for key in expected:
        assert rules.get(key) == "CASCADE", f"{key} is missing ON DELETE CASCADE"


# --- partial uniqueness ------------------------------------------------


def test_two_users_may_own_a_custom_brand_with_the_same_name(seeded: None) -> None:
    """The brand uniqueness indexes are partial, so custom names may repeat."""
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        with engine.begin() as connection:
            first = uuid4()
            second = uuid4()
            for user_id, email in ((first, "one@example.invalid"), (second, "two@example.invalid")):
                connection.execute(
                    text(
                        """
                        INSERT INTO users (id, email, display_name, is_demo,
                                           lifecycle_state, created_at, updated_at)
                        VALUES (:id, :email, 'Member', false, 'active', now(), now())
                        """
                    ),
                    {"id": user_id, "email": email},
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO brands (id, name, slug, owner_user_id, created_at, updated_at)
                        VALUES (:id, 'Indie House', 'indie-house', :owner, now(), now())
                        """
                    ),
                    {"id": uuid4(), "owner": user_id},
                )
    finally:
        engine.dispose()


def test_two_shared_brands_cannot_share_a_name(seeded: None) -> None:
    from sqlalchemy.exc import IntegrityError

    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO brands (id, name, slug, owner_user_id, created_at, updated_at)
                    VALUES (:id, 'ScentIQ Test Atelier', 'duplicate-slug', NULL, now(), now())
                    """
                ),
                {"id": uuid4()},
            )
    finally:
        engine.dispose()


# --- authentication ----------------------------------------------------


def test_request_without_a_token_is_unauthorized(client: TestClient) -> None:
    response = client.get("/api/v1/me")

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_expired_token_is_unauthorized(client: TestClient) -> None:
    import time

    stale = int(time.time()) - 3600
    response = client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token('user_a', iat=stale, exp=stale + 60)}"},
    )

    assert response.status_code == 401


def test_wrong_issuer_is_unauthorized(client: TestClient) -> None:
    response = client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token('user_a', iss='https://evil.invalid')}"},
    )

    assert response.status_code == 401


def test_authentication_fails_closed_when_unconfigured(seeded: None) -> None:
    """With no provider configured, protected routes refuse rather than allow."""
    with TestClient(create_app(unconfigured_settings())) as unconfigured:
        response = unconfigured.get("/api/v1/me", headers=auth_headers("user_a"))

    assert response.status_code == 503
    assert response.json()["code"] == "authentication_unavailable"


def test_first_request_provisions_a_user(client: TestClient) -> None:
    response = client.get(
        "/api/v1/me", headers=auth_headers("user_new", email="new@example.invalid")
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["email"] == "new@example.invalid"
    assert payload["lifecycle_state"] == "active"


def test_repeated_requests_reuse_the_same_user(client: TestClient) -> None:
    first = client.get("/api/v1/me", headers=auth_headers("user_same")).json()
    second = client.get("/api/v1/me", headers=auth_headers("user_same")).json()

    assert first["id"] == second["id"]

    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        with engine.connect() as connection:
            count = connection.execute(
                text("SELECT count(*) FROM user_identities WHERE subject = 'user_same'")
            ).scalar()
    finally:
        engine.dispose()

    assert count == 1


def test_token_without_an_email_claim_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/me", headers=auth_headers("user_no_email", email=None))

    assert response.status_code == 401


# --- authenticated journey ---------------------------------------------


def test_catalog_search_and_custom_creation(client: TestClient) -> None:
    headers = auth_headers("user_journey")

    listed = client.get("/api/v1/fragrances", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 15
    assert all(item["is_custom"] is False for item in listed.json())

    searched = client.get("/api/v1/fragrances", params={"q": "amber"}, headers=headers)
    assert searched.status_code == 200
    assert len(searched.json()) >= 1

    created = client.post(
        "/api/v1/fragrances",
        json={"brand_name": "My House", "name": "My Blend", "concentration": "extrait"},
        headers=headers,
    )
    assert created.status_code == 201
    assert created.json()["is_custom"] is True


def test_live_catalog_filters_discovery_and_owned_layering(client: TestClient) -> None:
    headers = auth_headers("user_live_catalog")
    filtered = client.get(
        "/api/v1/fragrances",
        params={"gender": "unisex", "family": "Woody", "sort": "rating"},
        headers=headers,
    )
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()] == [AMBER_ATLAS_ID]

    catalog = client.get("/api/v1/fragrances", headers=headers).json()
    owned_ids = [catalog[0]["id"], catalog[1]["id"]]
    for fragrance_id in owned_ids:
        added = client.post(
            "/api/v1/collection",
            json={"fragrance_id": fragrance_id, "ownership_type": "sample"},
            headers=headers,
        )
        assert added.status_code == 201

    discovered = client.get("/api/v1/discover", headers=headers)
    assert discovered.status_code == 200
    assert not ({item["fragrance"]["id"] for item in discovered.json()} & set(owned_ids))
    assert all("taste_match" in item and "redundancy_risk" in item for item in discovered.json())

    layering = client.get(
        "/api/v1/layering/suggestions",
        params={"mode": "contrast"},
        headers=headers,
    )
    assert layering.status_code == 200
    assert len(layering.json()) == 1
    assert {layering.json()[0]["first"]["id"], layering.json()[0]["second"]["id"]} == set(owned_ids)


def test_custom_fragrance_is_invisible_to_another_user(client: TestClient) -> None:
    created = client.post(
        "/api/v1/fragrances",
        json={"brand_name": "Private House", "name": "Private Blend", "concentration": "edp"},
        headers=auth_headers("user_owner"),
    )
    assert created.status_code == 201
    fragrance_id = created.json()["id"]

    other = client.get(f"/api/v1/fragrances/{fragrance_id}", headers=auth_headers("user_other"))

    assert other.status_code == 404


def test_collection_and_wear_journey(client: TestClient) -> None:
    headers = auth_headers("user_collector")

    added = client.post(
        "/api/v1/collection",
        json={
            "fragrance_id": AMBER_ATLAS_ID,
            "ownership_type": "bottle",
            "purchase_price": "129.50",
            "user_rating": 5,
        },
        headers=headers,
    )
    assert added.status_code == 201
    item = added.json()
    # Money is a decimal string, not a float.
    assert item["purchase_price"] == "129.50"
    assert "user_id" not in item

    logged = client.post(
        "/api/v1/wear-logs",
        json={"collection_item_id": item["id"], "worn_at": "2026-09-01T09:00:00Z"},
        headers=headers,
    )
    assert logged.status_code == 201

    insights = client.get("/api/v1/insights/collection", headers=headers)
    assert insights.status_code == 200
    assert insights.json()["total_items"] == 1
    assert insights.json()["total_wears"] == 1
    assert insights.json()["total_purchase_value"] == "129.50"

    retired = client.patch(
        f"/api/v1/collection/{item['id']}",
        json={"status": "finished"},
        headers=headers,
    )
    assert retired.status_code == 200
    assert retired.json()["status"] == "finished"

    # Retiring keeps the wear history.
    logs = client.get("/api/v1/wear-logs", headers=headers)
    assert len(logs.json()) == 1


def test_collection_is_isolated_between_users(client: TestClient) -> None:
    client.post(
        "/api/v1/collection",
        json={"fragrance_id": AMBER_ATLAS_ID, "ownership_type": "bottle"},
        headers=auth_headers("user_one"),
    )

    other = client.get("/api/v1/collection", headers=auth_headers("user_two"))

    assert other.status_code == 200
    assert other.json() == []


def test_profile_and_preferences_round_trip(client: TestClient) -> None:
    headers = auth_headers("user_profile")

    renamed = client.patch("/api/v1/me", json={"display_name": "Renamed"}, headers=headers)
    assert renamed.status_code == 200
    assert renamed.json()["display_name"] == "Renamed"

    preferences = client.patch(
        "/api/v1/me/preferences",
        json={"location": "Manchester", "preferred_season": "winter", "maximum_sprays": 4},
        headers=headers,
    )
    assert preferences.status_code == 200
    assert preferences.json()["location"] == "Manchester"

    fetched = client.get("/api/v1/me", headers=headers)
    assert fetched.json()["preferences"]["preferred_season"] == "winter"


def test_email_is_not_writable_through_the_profile(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/me",
        json={"display_name": "Someone", "email": "attacker@example.invalid"},
        headers=auth_headers("user_email"),
    )

    assert response.status_code == 422


def test_validation_failure_reports_field_errors(client: TestClient) -> None:
    response = client.post(
        "/api/v1/collection",
        json={"fragrance_id": AMBER_ATLAS_ID, "ownership_type": "bottle", "user_rating": 9},
        headers=auth_headers("user_validation"),
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "unprocessable_entity"
    assert any(error["field"] == "user_rating" for error in payload["field_errors"])


# --- deletion ----------------------------------------------------------


def test_deletion_flow_removes_owned_data_and_keeps_the_catalog(client: TestClient) -> None:
    headers = auth_headers("user_leaving")
    client.post(
        "/api/v1/collection",
        json={"fragrance_id": AMBER_ATLAS_ID, "ownership_type": "bottle"},
        headers=headers,
    )
    client.post(
        "/api/v1/fragrances",
        json={"brand_name": "Leaving House", "name": "Leaving Blend", "concentration": "edp"},
        headers=headers,
    )

    requested = client.post("/api/v1/me/deletion", headers=headers)
    assert requested.status_code == 202
    assert requested.json()["lifecycle_state"] == "deletion_pending"

    # A pending account is refused everywhere else.
    assert client.get("/api/v1/collection", headers=headers).status_code == 403

    applied = client.post(
        "/api/v1/internal/identity-events",
        json={
            "event_id": "evt_integration_1",
            "event_type": "user.deleted",
            "subject": "user_leaving",
        },
        headers={"x-scentiq-service-token": SERVICE_TOKEN},
    )
    assert applied.status_code == 200
    assert applied.json()["applied"] is True

    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT count(*) FROM user_identities WHERE subject = 'user_leaving'")
                ).scalar()
                == 0
            )
            # The curated catalog is untouched.
            assert (
                connection.execute(
                    text("SELECT count(*) FROM fragrances WHERE owner_user_id IS NULL")
                ).scalar()
                == 15
            )
            assert (
                connection.execute(
                    text("SELECT count(*) FROM fragrances WHERE owner_user_id IS NOT NULL")
                ).scalar()
                == 0
            )
    finally:
        engine.dispose()


def test_replayed_deletion_event_is_a_no_op(client: TestClient) -> None:
    client.get("/api/v1/me", headers=auth_headers("user_replay"))
    body = {
        "event_id": "evt_integration_replay",
        "event_type": "user.deleted",
        "subject": "user_replay",
    }
    service_headers = {"x-scentiq-service-token": SERVICE_TOKEN}

    first = client.post("/api/v1/internal/identity-events", json=body, headers=service_headers)
    second = client.post("/api/v1/internal/identity-events", json=body, headers=service_headers)

    assert first.json()["applied"] is True
    assert second.status_code == 200
    assert second.json()["applied"] is False


def test_identity_event_requires_the_service_token(client: TestClient) -> None:
    body = {"event_id": "evt_x", "event_type": "user.deleted", "subject": "user_a"}

    missing = client.post("/api/v1/internal/identity-events", json=body)
    wrong = client.post(
        "/api/v1/internal/identity-events",
        json=body,
        headers={"x-scentiq-service-token": "not-the-token"},
    )

    assert missing.status_code == 401
    assert wrong.status_code == 401


def test_identity_event_rejects_a_user_session_token(client: TestClient) -> None:
    """The internal endpoint must not accept a user's session token."""
    response = client.post(
        "/api/v1/internal/identity-events",
        json={"event_id": "evt_y", "event_type": "user.deleted", "subject": "user_a"},
        headers=auth_headers("user_a"),
    )

    assert response.status_code == 401


def test_deletion_can_be_rolled_back(client: TestClient) -> None:
    headers = auth_headers("user_rollback")
    client.get("/api/v1/me", headers=headers)
    client.post("/api/v1/me/deletion", headers=headers)

    cancelled = client.post("/api/v1/me/deletion/cancel", headers=headers)

    assert cancelled.status_code == 204
    # Usable again once the rollback has run.
    assert client.get("/api/v1/collection", headers=headers).status_code == 200
