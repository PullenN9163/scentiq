"""PostgreSQL wear intelligence persistence and authenticated BFF contract."""

import os
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from auth_harness import auth_headers, resolver, settings
from catalog_fixture import load_test_catalog
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from scentiq_api.main import create_app
from scentiq_api.models import Recommendation, RecommendationDecision, WearFeedback, WearLog

pytestmark = pytest.mark.integration


def test_recommendation_decision_wear_feedback_and_foreign_member_contract() -> None:
    root = Path(__file__).parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(config, "head")
    load_test_catalog()
    with TestClient(create_app(settings(), signing_key_resolver=resolver())) as client:
        headers = auth_headers("wear-intelligence-member")
        other = auth_headers("wear-intelligence-foreign")
        created = client.post(
            "/api/v1/collection",
            headers=headers,
            json={
                "fragrance_id": "10000000-0000-4000-8000-000000000001",
                "ownership_type": "bottle",
                "status": "owned",
            },
        )
        assert created.status_code == 201, created.text
        response = client.get("/api/v1/recommendations/today", headers=headers)
        assert response.status_code == 200, response.text
        recommendation = response.json()["recommendations"][0]
        repeated = client.get("/api/v1/recommendations/today", headers=headers).json()
        assert repeated["recommendations"][0]["id"] == recommendation["id"]
        assert (
            client.post(
                f"/api/v1/recommendations/{recommendation['id']}/decision",
                headers=other,
                json={"action": "accepted"},
            ).status_code
            == 404
        )
        logged = client.post(
            f"/api/v1/recommendations/{recommendation['id']}/wear",
            headers=headers,
            json={"sprays": 3},
        )
        assert logged.status_code == 200, logged.text
        wear_id = logged.json()["id"]
        assert logged.json()["recommendation_id"] == recommendation["id"]
        assert (
            client.put(
                f"/api/v1/wear-logs/{wear_id}/feedback",
                headers=headers,
                json={"rating": 5, "longevity": 8, "projection": "moderate"},
            ).status_code
            == 200
        )
        assert client.get(f"/api/v1/wear-logs/{wear_id}/feedback", headers=other).status_code == 404
        assert (
            client.post(
                "/api/v1/recommendations/preview", headers=headers, json={"user_id": "someone-else"}
            ).status_code
            == 422
        )
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        with Session(engine) as session:
            record = session.get(Recommendation, UUID(recommendation["id"]))
            assert record is not None
            decision = session.scalar(
                select(RecommendationDecision).where(
                    RecommendationDecision.recommendation_id == record.id
                )
            )
            assert decision is not None and decision.action == "accepted"
            assert session.get(WearLog, UUID(wear_id)) is not None
            assert (
                session.scalar(
                    select(WearFeedback).where(WearFeedback.wear_log_id == UUID(wear_id))
                )
                is not None
            )
            # Member deletion cascades through recommendation/candidate/decision/feedback.
            user_id = record.user_id
            session.execute(text("DELETE FROM users WHERE id=:id"), {"id": user_id})
            session.commit()
            session.expire_all()
            assert session.get(Recommendation, UUID(recommendation["id"])) is None
            assert session.get(WearLog, UUID(wear_id)) is None
    finally:
        engine.dispose()
