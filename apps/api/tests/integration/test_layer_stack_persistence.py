"""PostgreSQL coverage for normalized layering and legacy pair migration."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from auth_harness import auth_headers, resolver, settings
from domain_fixtures import make_brand, make_collection_item, make_fragrance, make_user
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from scentiq_api.main import create_app
from scentiq_api.models import LayeringLog, User, WearLog
from scentiq_api.models.layer_stacks import LayerStack, LayerStackItem, LayerStackWear

pytestmark = pytest.mark.integration
API_ROOT = Path(__file__).parents[2]


def migration_config() -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    return config


def test_saved_triple_api_history_isolation_and_account_cascade() -> None:
    config = migration_config()
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        with Session(engine) as session:
            user = make_user(session, email="layer-owner@example.test", subject="layer-owner")
            make_user(session, email="layer-other@example.test", subject="layer-other")
            brand = make_brand(session, name="Layer integration")
            fragrances = [
                make_fragrance(session, brand=brand, name=f"Owned scent {index}")
                for index in range(3)
            ]
            for fragrance in fragrances:
                make_collection_item(session, user=user, fragrance=fragrance)
            ids = [str(fragrance.id) for fragrance in fragrances]
            user_id = user.id
            session.commit()
        owner = auth_headers("layer-owner")
        other = auth_headers("layer-other")
        with TestClient(create_app(settings(), signing_key_resolver=resolver())) as client:
            saved = client.post(
                "/api/v1/layering/stacks",
                headers=owner,
                json={"fragrance_ids": ids, "name": "Evening stack", "mode": "balanced"},
            )
            assert saved.status_code == 201, saved.text
            stack_id = saved.json()["id"]
            assert len(saved.json()["suggestion"]["items"]) == 3
            assert (
                client.post(
                    "/api/v1/layering/stacks/evaluate", headers=other, json={"fragrance_ids": ids}
                ).status_code
                == 404
            )
            assert client.get("/api/v1/layering/stacks", headers=other).json() == []
            assert (
                client.patch(
                    f"/api/v1/layering/stacks/{stack_id}", headers=other, json={"name": "Other"}
                ).status_code
                == 404
            )
            renamed = client.patch(
                f"/api/v1/layering/stacks/{stack_id}",
                headers=owner,
                json={"name": "Renamed evening"},
            )
            assert renamed.json()["name"] == "Renamed evening"
            wear = client.post(
                f"/api/v1/layering/stacks/{stack_id}/wears",
                headers=owner,
                json={"rating": 5, "notes": "Warm and subtle"},
            )
            assert wear.status_code == 201, wear.text
            wear_id = wear.json()["id"]
            assert (
                client.get(f"/api/v1/layering/stacks/{stack_id}/wears", headers=other).status_code
                == 404
            )
            assert (
                client.patch(
                    f"/api/v1/layering/stacks/{stack_id}/wears/{wear_id}/rating",
                    headers=other,
                    json={"rating": 1},
                ).status_code
                == 404
            )
            rated = client.patch(
                f"/api/v1/layering/stacks/{stack_id}/wears/{wear_id}/rating",
                headers=owner,
                json={"rating": 4},
            )
            assert rated.json()["rating"] == 4
            listing = client.get("/api/v1/layering/stacks", headers=owner).json()
            assert listing[0]["wear_count"] == 1
            assert listing[0]["average_rating"] == 4
            assert (
                client.get("/api/v1/insights/collection", headers=owner).json()["total_wears"] == 3
            )
            duplicate = client.post(
                "/api/v1/layering/stacks",
                headers=owner,
                json={"fragrance_ids": ids[:2], "name": "Pair"},
            )
            assert duplicate.status_code == 201
            assert (
                client.delete(
                    f"/api/v1/layering/stacks/{duplicate.json()['id']}", headers=owner
                ).status_code
                == 204
            )
        with Session(engine) as session:
            stored = session.scalar(select(LayerStack))
            assert stored is not None and stored.algorithm_version == "layering-v2"
            session.execute(delete(User).where(User.id == user_id))
            session.commit()
            assert session.scalar(select(func.count()).select_from(LayerStack)) == 0
            assert session.scalar(select(func.count()).select_from(LayerStackItem)) == 0
            assert session.scalar(select(func.count()).select_from(LayerStackWear)) == 0
            assert session.scalar(select(func.count()).select_from(WearLog)) == 0
    finally:
        engine.dispose()


def test_legacy_pair_wear_rating_and_notes_survive_upgrade_and_roundtrip() -> None:
    config = migration_config()
    command.downgrade(config, "base")
    command.upgrade(config, "20261007_0007_wear_intelligence")
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        with Session(engine) as session:
            user = make_user(session, email="legacy-layer@example.test")
            brand = make_brand(session, name="Legacy layer")
            first = make_fragrance(session, brand=brand, name="Legacy first")
            second = make_fragrance(session, brand=brand, name="Legacy second")
            worn_at = datetime(2026, 9, 10, 12, tzinfo=UTC)
            session.add(
                LayeringLog(
                    user_id=user.id,
                    primary_fragrance_id=first.id,
                    secondary_fragrance_id=second.id,
                    worn_at=worn_at,
                    rating=4,
                    notes="Original private note",
                )
            )
            session.commit()
        for _ in range(2):
            command.upgrade(config, "head")
            with Session(engine) as session:
                assert session.scalar(select(func.count()).select_from(LayerStack)) == 1
                stack = session.scalar(select(LayerStack))
                assert stack is not None and stack.algorithm_version == "legacy-pair-v1"
                assert session.scalar(select(func.count()).select_from(LayerStackItem)) == 2
                wear = session.scalar(select(LayerStackWear))
                assert wear is not None
                assert wear.rating == 4 and wear.notes == "Original private note"
                assert wear.worn_at == worn_at
            command.downgrade(config, "20261007_0007_wear_intelligence")
        command.upgrade(config, "head")
    finally:
        engine.dispose()
