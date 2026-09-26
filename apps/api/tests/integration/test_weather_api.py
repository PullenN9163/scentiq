"""The weather endpoints over HTTP against PostgreSQL, with a fake provider."""

from __future__ import annotations

import os
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from auth_harness import auth_headers, resolver, settings
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from scentiq_api.integrations.weather import DailyForecast, Place, WeatherProviderError
from scentiq_api.main import create_app

pytestmark = pytest.mark.integration

API_ROOT = Path(__file__).parents[2]


class FakeProvider:
    def __init__(self) -> None:
        self.fail = False
        self.places = [
            Place(
                name="Leeds",
                latitude=Decimal("53.79648"),
                longitude=Decimal("-1.54785"),
                timezone="Europe/London",
                admin1="England",
                country="United Kingdom",
                country_code="GB",
            )
        ]

    def geocode(self, query: str) -> list[Place]:
        if self.fail:
            raise WeatherProviderError("down")
        return self.places if query.startswith("Leeds") else []

    def daily_forecast(
        self, latitude: Decimal, longitude: Decimal, timezone: str | None, days: int = 7
    ) -> list[DailyForecast]:
        if self.fail:
            raise WeatherProviderError("down")
        # Start yesterday so "today" is always inside the window, whatever the
        # clock says when the suite runs.
        start = date.today() - timedelta(days=1)
        return [
            DailyForecast(
                day=start + timedelta(days=offset),
                weather_code=3,
                temperature_max_celsius=Decimal("17.25"),
                temperature_min_celsius=Decimal("8.5"),
                precipitation_probability=Decimal("0.100"),
                humidity=66,
            )
            for offset in range(days + 1)
        ]


def _reset_database() -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def client(provider: FakeProvider) -> TestClient:
    _reset_database()
    return TestClient(
        create_app(settings(), signing_key_resolver=resolver(), weather_provider=provider)
    )


def _save_preferences(client: TestClient, subject: str, **values: object) -> dict[str, object]:
    response = client.patch("/api/v1/me/preferences", json=values, headers=auth_headers(subject))
    return {"status": response.status_code, **response.json()}


def test_forecast_journey(client: TestClient, provider: FakeProvider) -> None:
    headers = auth_headers("user_weather")

    missing = client.get("/api/v1/weather/forecast", headers=headers)
    assert missing.status_code == 409
    assert missing.json()["code"] == "location_required"

    unknown = _save_preferences(client, "user_weather", location="Atlantis")
    assert unknown["status"] == 422
    field_error = unknown["field_errors"][0]  # type: ignore[index]
    assert field_error["field"] == "location"
    assert field_error["code"] == "location_not_found"

    saved = _save_preferences(
        client, "user_weather", location="Leeds, UK", temperature_unit="celsius"
    )
    assert saved["status"] == 200
    assert saved["location_label"] == "Leeds, England, United Kingdom"
    assert saved["timezone"] == "Europe/London"
    assert saved["temperature_unit"] == "celsius"

    first = client.get("/api/v1/weather/forecast", headers=headers)
    assert first.status_code == 200
    body = first.json()
    assert body["stale"] is False
    assert body["temperature_unit"] == "celsius"
    assert len(body["days"]) == 7
    assert body["days"][0]["condition"] == "cloudy"
    assert body["days"][0]["high_celsius"] == 17.25

    # Served from the cache; still correct when the provider disappears.
    provider.fail = True
    cached = client.get("/api/v1/weather/forecast", headers=headers)
    assert cached.status_code == 200
    assert cached.json()["stale"] is False

    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE weather_snapshots SET fetched_at = now() - interval '2 hours'")
            )
            count = connection.execute(text("SELECT count(*) FROM weather_snapshots")).scalar_one()
    finally:
        engine.dispose()
    assert count >= 7

    stale = client.get("/api/v1/weather/forecast", headers=headers)
    assert stale.status_code == 200
    assert stale.json()["stale"] is True


def test_refreshing_upserts_one_row_per_day(client: TestClient, provider: FakeProvider) -> None:
    headers = auth_headers("user_refresh")
    _save_preferences(client, "user_refresh", location="Leeds")
    client.get("/api/v1/weather/forecast", headers=headers)

    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE weather_snapshots SET fetched_at = now() - interval '2 hours'")
            )
        refreshed = client.get("/api/v1/weather/forecast", headers=headers)
        with engine.connect() as connection:
            duplicates = connection.execute(
                text(
                    "SELECT count(*) FROM (SELECT user_id, forecast_at FROM weather_snapshots "
                    "GROUP BY user_id, forecast_at HAVING count(*) > 1) AS d"
                )
            ).scalar_one()
    finally:
        engine.dispose()

    assert refreshed.status_code == 200
    assert refreshed.json()["stale"] is False
    assert duplicates == 0


def test_provider_outage_with_nothing_cached_is_unavailable(
    client: TestClient, provider: FakeProvider
) -> None:
    _save_preferences(client, "user_outage", location="Leeds")
    provider.fail = True

    response = client.get("/api/v1/weather/forecast", headers=auth_headers("user_outage"))

    assert response.status_code == 503
    assert response.json()["code"] == "weather_unavailable"


def test_place_search(client: TestClient) -> None:
    response = client.get(
        "/api/v1/weather/places", params={"q": "Leeds"}, headers=auth_headers("user_places")
    )
    assert response.status_code == 200
    assert response.json()[0]["label"] == "Leeds, England, United Kingdom"
