"""Real PostgreSQL row-lock guarantees for recommendation browsing."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from domain_fixtures import make_brand, make_collection_item, make_fragrance, make_user
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from scentiq_api.models import Brand, Fragrance, User
from scentiq_api.schemas.wear_recommendations import (
    RecommendationNextRequest,
    WearRecommendationResponse,
)
from scentiq_api.services.recommendation_choices import RecommendationChoiceService
from scentiq_api.services.wear_recommendations import WearRecommendationService

pytestmark = pytest.mark.integration


def test_concurrent_next_requests_advance_once_and_cascade() -> None:
    root = Path(__file__).parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(config, "head")
    engine = create_engine(os.environ["DATABASE_URL"])
    token = uuid4().hex
    with Session(engine) as session:
        user = make_user(session, email=f"choices-{token}@example.test")
        brand = make_brand(session, name=f"Choices {token}")
        for index in range(3):
            make_collection_item(
                session,
                user=user,
                fragrance=make_fragrance(session, brand=brand, name=f"Choice {index}"),
            )
        recommendation = (
            WearRecommendationService(session, clock=lambda: datetime(2026, 10, 20, 12, tzinfo=UTC))
            .today(user.id)
            .recommendations[0]
        )
        user_id, brand_id = user.id, brand.id
        session.commit()
    try:
        request = RecommendationNextRequest(
            idempotency_key=uuid4(), expected_fragrance_id=recommendation.fragrance.id
        )

        def advance(_: int) -> WearRecommendationResponse:
            with Session(engine) as session:
                result = RecommendationChoiceService(session).next(
                    user_id, recommendation.id, request
                )
                session.commit()
                return result

        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = list(pool.map(advance, range(2)))
        assert first.fragrance.id == second.fragrance.id != recommendation.fragrance.id
        assert first.remaining_options == second.remaining_options == 1
        with Session(engine) as session:
            restored = RecommendationChoiceService(session).current(
                user_id,
                WearRecommendationService(session)._response(
                    user_id, WearRecommendationService(session).get(user_id, recommendation.id)
                ),
            )
            assert restored.fragrance.id == first.fragrance.id
    finally:
        with Session(engine) as session:
            session.execute(delete(User).where(User.id == user_id))
            session.execute(delete(Fragrance).where(Fragrance.brand_id == brand_id))
            session.execute(delete(Brand).where(Brand.id == brand_id))
            session.commit()
        engine.dispose()
