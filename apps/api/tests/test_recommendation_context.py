from datetime import UTC, datetime, timedelta
from decimal import Decimal

from domain_fixtures import make_user
from sqlalchemy.orm import Session

from scentiq_api.models import UserPreference, WeatherSnapshot


def test_context_uses_event_hour_and_discloses_daily_fallback(session: Session) -> None:
    from scentiq_api.services.recommendation_context import RecommendationContextBuilder

    user = make_user(session, email="context@example.com")
    now = datetime(2026, 10, 20, 23, tzinfo=UTC)
    session.add(
        UserPreference(
            user_id=user.id,
            timezone="America/New_York",
            location_label="New York",
            latitude=Decimal("40"),
        )
    )
    weather = WeatherSnapshot(
        user_id=user.id,
        location_label="New York",
        forecast_at=now.replace(hour=0),
        temperature_celsius=30,
        condition="clear",
        source="test",
        fetched_at=now,
        hourly_forecast=[
            {
                "at": now.isoformat(),
                "temperature_celsius": 15,
                "humidity": 80,
                "condition": "rain",
                "precipitation_probability": 0.9,
            }
        ],
    )
    session.add(weather)
    session.flush()
    builder = RecommendationContextBuilder(session, clock=lambda: now)
    context = builder.build(user.id, now, source="event", key="test")
    assert context["high_celsius"] == 15
    assert context["daypart"] == "night"
    assert context["weather_resolution"] == "hourly"
    assert context["weather_stale"] is False
    context = builder.build(user.id, now - timedelta(hours=3), source="day", key="test")
    assert context["high_celsius"] == 30
    assert context["weather_resolution"] == "daily"


def test_context_excludes_wrong_location_weather(session: Session) -> None:
    from scentiq_api.services.recommendation_context import RecommendationContextBuilder

    user = make_user(session, email="moved@example.com")
    now = datetime(2026, 10, 20, tzinfo=UTC)
    session.add(UserPreference(user_id=user.id, location_label="Paris"))
    session.add(
        WeatherSnapshot(
            user_id=user.id,
            location_label="New York",
            forecast_at=now,
            temperature_celsius=30,
            condition="clear",
            source="test",
        )
    )
    session.flush()
    context = RecommendationContextBuilder(session).build(user.id, now, source="day", key="x")
    assert context["high_celsius"] is None
    assert context["weather_resolution"] == "unavailable"


def test_context_stale_fallback_and_southern_season(session: Session) -> None:
    from scentiq_api.services.recommendation_context import RecommendationContextBuilder

    user = make_user(session, email="south@example.com")
    now = datetime(2026, 12, 20, 22, tzinfo=UTC)
    session.add(
        UserPreference(
            user_id=user.id,
            timezone="Australia/Sydney",
            location_label="Sydney",
            latitude=Decimal("-33"),
        )
    )
    session.add(
        WeatherSnapshot(
            user_id=user.id,
            location_label="Sydney",
            forecast_at=datetime(2026, 12, 21, tzinfo=UTC),
            temperature_celsius=30,
            condition="clear",
            source="test",
            fetched_at=now - timedelta(hours=2),
        )
    )
    session.flush()
    context = RecommendationContextBuilder(session, clock=lambda: now).build(
        user.id, now, source="today", key="test"
    )
    assert context["season"] == "summer"
    assert context["daypart"] == "day"
    assert context["weather_stale"] is True
    assert context["weather_resolution"] == "daily"


def test_repeated_dst_hour_selects_exact_utc_hour(session: Session) -> None:
    from scentiq_api.services.recommendation_context import RecommendationContextBuilder

    user = make_user(session, email="dst@example.com")
    first = datetime(2026, 11, 1, 5, tzinfo=UTC)
    second = first + timedelta(hours=1)
    session.add(
        UserPreference(user_id=user.id, timezone="America/New_York", location_label="New York")
    )
    session.add(
        WeatherSnapshot(
            user_id=user.id,
            location_label="New York",
            forecast_at=first.replace(hour=0),
            temperature_celsius=30,
            condition="clear",
            source="test",
            fetched_at=first,
            hourly_forecast=[
                {"at": first.isoformat(), "temperature_celsius": 10},
                {"at": second.isoformat(), "temperature_celsius": 11},
            ],
        )
    )
    session.flush()
    builder = RecommendationContextBuilder(session, clock=lambda: first)
    assert builder.build(user.id, first, source="event", key="a")["high_celsius"] == 10
    assert builder.build(user.id, second, source="event", key="b")["high_celsius"] == 11


def test_event_window_uses_conservative_weather_across_midnight(session: Session) -> None:
    from scentiq_api.services.recommendation_context import RecommendationContextBuilder

    user = make_user(session, email="window@example.com")
    now = datetime(2026, 10, 20, 23, 30, tzinfo=UTC)
    session.add(UserPreference(user_id=user.id, timezone="UTC", location_label="Leeds"))
    for offset, temp, humidity, probability, condition in [
        (0, 15, 50, 0, "clear"),
        (1, 25, 90, 0.8, "rain"),
    ]:
        hour = now.replace(minute=0) + timedelta(hours=offset)
        session.add(
            WeatherSnapshot(
                user_id=user.id,
                location_label="Leeds",
                forecast_at=hour.replace(hour=0),
                temperature_celsius=30,
                condition="clear",
                source="test",
                fetched_at=now,
                hourly_forecast=[
                    {
                        "at": hour.isoformat(),
                        "temperature_celsius": temp,
                        "humidity": humidity,
                        "precipitation_probability": probability,
                        "condition": condition,
                    }
                ],
            )
        )
    session.flush()
    context = RecommendationContextBuilder(session, clock=lambda: now).build(
        user.id, now, source="event", key="window", duration_minutes=60
    )
    assert context["duration_minutes"] == 60
    assert context["high_celsius"] == 25
    assert context["low_celsius"] == 15
    assert context["humidity"] == 90
    assert context["precipitation_probability"] == 0.8
    assert context["condition"] == "rain"
    assert context["weather_resolution"] == "hourly"
