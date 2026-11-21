"""Regression cases for recommendation calendar/weather integration."""

from datetime import UTC, datetime, timedelta

import pytest
from domain_fixtures import make_brand, make_collection_item, make_fragrance, make_user
from sqlalchemy.orm import Session

from scentiq_api.models import (
    CalendarEvent,
    User,
    UserCollectionItem,
    UserPreference,
    WeatherSnapshot,
)
from scentiq_api.schemas.wear_recommendations import RecommendationDecisionRequest
from scentiq_api.services.wear_recommendations import WearRecommendationService


def collection(session: Session, *, timezone: str = "UTC") -> tuple[User, list[UserCollectionItem]]:
    user = make_user(session, email="context-review@example.test")
    session.add(UserPreference(user_id=user.id, timezone=timezone, location_label="Saved place"))
    brand = make_brand(session, name="Context review")
    items = [
        make_collection_item(
            session, user=user, fragrance=make_fragrance(session, brand=brand, name=name)
        )
        for name in ("Alpha", "Beta")
    ]
    session.flush()
    return user, items


def test_general_pick_uses_upcoming_event_weather_window(session: Session) -> None:
    user, _ = collection(session)
    now = datetime(2026, 10, 20, 12, tzinfo=UTC)
    event = CalendarEvent(
        user_id=user.id,
        title="Work",
        event_type="work",
        is_hidden=False,
        starts_at=now + timedelta(hours=2),
        ends_at=now + timedelta(hours=4),
    )
    session.add(event)
    session.add(
        WeatherSnapshot(
            user_id=user.id,
            location_label="Saved place",
            forecast_at=now.replace(hour=0),
            temperature_celsius=40,
            condition="clear",
            source="test",
            fetched_at=now,
            hourly_forecast=[
                {"at": now.isoformat(), "temperature_celsius": 10},
                {"at": (now + timedelta(hours=2)).isoformat(), "temperature_celsius": 20},
                {"at": (now + timedelta(hours=3)).isoformat(), "temperature_celsius": 30},
            ],
        )
    )
    session.flush()
    response = (
        WearRecommendationService(session, clock=lambda: now).today(user.id).recommendations[0]
    )
    assert response.context.calendar_event_id == event.id
    assert response.context.high_celsius == 30
    assert response.context.duration_minutes == 120
    assert response.context.recommended_for == event.starts_at


def test_all_day_event_uses_its_logical_calendar_date(session: Session) -> None:
    user, _ = collection(session, timezone="America/New_York")
    now = datetime(2026, 10, 20, 15, tzinfo=UTC)
    event = CalendarEvent(
        user_id=user.id,
        title="Formal day",
        event_type="formal",
        is_hidden=False,
        starts_at=now.replace(hour=0),
        ends_at=now.replace(hour=0) + timedelta(days=1),
        is_all_day=True,
    )
    session.add(event)
    session.flush()
    response = (
        WearRecommendationService(session, clock=lambda: now).today(user.id).recommendations[0]
    )
    assert response.context.calendar_event_id == event.id
    assert response.context.occasion == "formal"
    assert response.context.local_date == now.date()


def test_ongoing_overnight_event_is_part_of_current_day(session: Session) -> None:
    user, _ = collection(session, timezone="America/New_York")
    now = datetime(2026, 10, 20, 5, 30, tzinfo=UTC)
    event = CalendarEvent(
        user_id=user.id,
        title="Night work",
        event_type="work",
        is_hidden=False,
        starts_at=now.replace(hour=3, minute=0),
        ends_at=now.replace(hour=7, minute=0),
    )
    session.add(event)
    session.flush()
    response = (
        WearRecommendationService(session, clock=lambda: now).today(user.id).recommendations[0]
    )
    assert response.context.calendar_event_id == event.id
    assert response.context.occasion == "work"
    assert response.context.recommended_for == now
    assert response.context.duration_minutes == 90


def test_ongoing_event_reload_preserves_current_choice_within_hour(session: Session) -> None:
    from uuid import uuid4

    from scentiq_api.schemas.wear_recommendations import RecommendationNextRequest
    from scentiq_api.services.recommendation_choices import RecommendationChoiceService

    user, _ = collection(session, timezone="America/New_York")
    now = datetime(2026, 10, 20, 5, 30, tzinfo=UTC)
    session.add(
        CalendarEvent(
            user_id=user.id,
            title="Night work",
            event_type="work",
            is_hidden=False,
            starts_at=now.replace(hour=3, minute=0),
            ends_at=now.replace(hour=7, minute=0),
        )
    )
    session.flush()
    initial = (
        WearRecommendationService(session, clock=lambda: now).today(user.id).recommendations[0]
    )
    selected = RecommendationChoiceService(session).next(
        user.id, initial.id, RecommendationNextRequest(idempotency_key=uuid4())
    )
    later = (
        WearRecommendationService(session, clock=lambda: now + timedelta(minutes=15))
        .today(user.id)
        .recommendations[0]
    )
    assert later.id == initial.id
    assert later.fragrance.id == selected.fragrance.id


@pytest.mark.parametrize("retire_all", [False, True])
def test_accepted_ineligible_selection_regenerates_without_phantom_lock(
    session: Session, retire_all: bool
) -> None:
    user, items = collection(session)
    now = datetime(2026, 10, 20, 12, tzinfo=UTC)
    service = WearRecommendationService(session, clock=lambda: now)
    accepted = service.today(user.id).recommendations[0]
    service.decide(user.id, accepted.id, RecommendationDecisionRequest(action="accepted"))
    for item in items:
        if retire_all or item.fragrance_id == accepted.fragrance.id:
            item.status = "sold"
    if retire_all:
        make_collection_item(
            session,
            user=user,
            fragrance=make_fragrance(
                session,
                brand=make_brand(session, name="New collection"),
                name="New eligible fragrance",
            ),
        )
    session.flush()
    current = service.today(user.id).recommendations[0]
    assert current.id != accepted.id
    assert current.fragrance.id != accepted.fragrance.id
    assert current.decision is None
