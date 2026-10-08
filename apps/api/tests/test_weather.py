"""Open-Meteo parsing, location resolution and the cached forecast."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
from domain_fixtures import make_user
from sqlalchemy.orm import Session

from scentiq_api.errors import ApiError
from scentiq_api.integrations.weather import (
    DailyForecast,
    OpenMeteoClient,
    Place,
    WeatherProviderError,
    condition_for_code,
)
from scentiq_api.models import WeatherSnapshot
from scentiq_api.repositories import UserRepository, WeatherRepository
from scentiq_api.schemas import PreferencesUpdateRequest
from scentiq_api.services import ProfileService, WeatherService

NOW = datetime(2026, 9, 26, 15, 0, tzinfo=UTC)

LEEDS = Place(
    name="Leeds",
    latitude=Decimal("53.79648"),
    longitude=Decimal("-1.54785"),
    timezone="Europe/London",
    admin1="England",
    country="United Kingdom",
    country_code="GB",
)


class FakeProvider:
    """An in-memory WeatherProvider that records calls and can be made to fail."""

    def __init__(self, places: list[Place] | None = None) -> None:
        self.places = [LEEDS] if places is None else places
        self.fail = False
        self.geocode_calls: list[str] = []
        self.forecast_calls = 0

    def geocode(self, query: str) -> list[Place]:
        self.geocode_calls.append(query)
        if self.fail:
            raise WeatherProviderError("down")
        return self.places

    def daily_forecast(
        self,
        latitude: Decimal,
        longitude: Decimal,
        timezone: str | None,
        days: int = 7,
    ) -> list[DailyForecast]:
        self.forecast_calls += 1
        if self.fail:
            raise WeatherProviderError("down")
        start = date(2026, 9, 26)
        return [
            DailyForecast(
                day=start + timedelta(days=offset),
                weather_code=61 if offset == 1 else 0,
                temperature_max_celsius=Decimal("18.5") + offset,
                temperature_min_celsius=Decimal("9.0"),
                precipitation_probability=Decimal("0.400"),
                humidity=70,
            )
            for offset in range(days)
        ]


def _service(session: Session, provider: FakeProvider, now: datetime = NOW) -> WeatherService:
    return WeatherService(
        UserRepository(session),
        WeatherRepository(session),
        provider,
        clock=lambda: now,
    )


def _save_location(session: Session, user_id: Any, provider: FakeProvider, location: str) -> None:
    ProfileService(UserRepository(session), provider).replace_preferences(
        user_id, PreferencesUpdateRequest(location=location)
    )


# --- condition mapping -------------------------------------------------


@pytest.mark.parametrize(
    ("code", "condition"),
    [
        (0, "clear"),
        (2, "partly_cloudy"),
        (3, "cloudy"),
        (45, "fog"),
        (53, "drizzle"),
        (63, "rain"),
        (81, "rain"),
        (73, "snow"),
        (86, "snow"),
        (95, "thunderstorm"),
        (4, "unknown"),
        (None, "unknown"),
    ],
)
def test_wmo_codes_map_to_conditions(code: int | None, condition: str) -> None:
    assert condition_for_code(code) == condition


# --- Open-Meteo client --------------------------------------------------


def _client(handler: Any, *, api_key: str | None = None) -> OpenMeteoClient:
    return OpenMeteoClient(
        forecast_base_url="https://forecast.test",
        geocoding_base_url="https://geocoding.test",
        api_key=api_key,
        transport=httpx.MockTransport(handler),
    )


_GEOCODING_RESULTS = {
    "results": [
        {
            "name": "Manchester",
            "latitude": 42.99564,
            "longitude": -71.45479,
            "timezone": "America/New_York",
            "admin1": "New Hampshire",
            "country": "United States",
            "country_code": "US",
        },
        {
            "name": "Manchester",
            "latitude": 53.48095,
            "longitude": -2.23743,
            "timezone": "Europe/London",
            "admin1": "England",
            "country": "United Kingdom",
            "country_code": "GB",
        },
    ]
}


def test_geocode_searches_the_bare_name_and_prefers_the_qualifier() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_GEOCODING_RESULTS)

    places = _client(handler).geocode("Manchester, UK")

    assert seen[0].url.host == "geocoding.test"
    assert seen[0].url.params["name"] == "Manchester"
    assert places[0].country_code == "GB"
    assert places[0].label == "Manchester, England, United Kingdom"
    assert places[0].timezone == "Europe/London"


def test_geocode_keeps_provider_order_without_a_qualifier() -> None:
    places = _client(lambda _: httpx.Response(200, json=_GEOCODING_RESULTS)).geocode("Manchester")
    assert [place.country_code for place in places] == ["US", "GB"]


def test_geocode_with_no_results_is_empty() -> None:
    assert _client(lambda _: httpx.Response(200, json={})).geocode("Nowhereville") == []


def test_geocode_blank_query_does_not_call_the_provider() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("provider should not be called")

    assert _client(handler).geocode(" , ") == []


def test_api_key_is_sent_when_configured() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={})

    _client(handler, api_key="commercial-key").geocode("Leeds")
    assert seen[0].url.params["apikey"] == "commercial-key"


def test_provider_errors_do_not_leak_the_url() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    with pytest.raises(WeatherProviderError) as error:
        _client(handler, api_key="secret-key").geocode("Leeds")
    assert "secret-key" not in str(error.value)


def test_timeouts_become_provider_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow", request=request)

    with pytest.raises(WeatherProviderError):
        _client(handler).daily_forecast(Decimal("53.8"), Decimal("-1.5"), "Europe/London")


def test_daily_forecast_parses_columns_and_skips_days_without_a_high() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "daily": {
                    "time": ["2026-09-26", "2026-09-27", "2026-09-28"],
                    "weather_code": [0, 63, None],
                    "temperature_2m_max": [19.4, 14.1, None],
                    "temperature_2m_min": [8.2, None, 7.0],
                    "precipitation_probability_max": [5, 90, None],
                    "relative_humidity_2m_mean": [71.6, None, 80],
                }
            },
        )

    forecasts = _client(handler).daily_forecast(Decimal("53.8"), Decimal("-1.5"), "Europe/London")

    assert seen[0].url.params["timezone"] == "Europe/London"
    assert seen[0].url.params["temperature_unit"] == "celsius"
    assert [forecast.day for forecast in forecasts] == [date(2026, 9, 26), date(2026, 9, 27)]
    assert forecasts[0].temperature_max_celsius == Decimal("19.4")
    assert forecasts[0].precipitation_probability == Decimal("0.050")
    assert forecasts[0].humidity == 72
    assert forecasts[1].weather_code == 63
    assert forecasts[1].temperature_min_celsius is None


def test_daily_forecast_rejects_an_unexpected_payload() -> None:
    with pytest.raises(WeatherProviderError):
        _client(lambda _: httpx.Response(200, json={"daily": "nope"})).daily_forecast(
            Decimal("1"), Decimal("1"), None
        )


# --- saving a location --------------------------------------------------


def test_saving_a_location_resolves_it(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeProvider()

    stored = ProfileService(UserRepository(session), provider).replace_preferences(
        user.id, PreferencesUpdateRequest(location="Leeds", temperature_unit="celsius")
    )

    assert stored.location == "Leeds"
    assert stored.location_label == "Leeds, England, United Kingdom"
    assert stored.timezone == "Europe/London"
    assert stored.temperature_unit == "celsius"


def test_an_unknown_location_is_refused_without_changing_preferences(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeProvider()
    _save_location(session, user.id, provider, "Leeds")
    provider.places = []

    with pytest.raises(ApiError) as error:
        _save_location(session, user.id, provider, "Nowhereville")

    assert error.value.status_code == 422
    assert error.value.field_errors is not None
    assert error.value.field_errors[0].field == "location"
    preferences = UserRepository(session).get_preferences(user.id)
    assert preferences is not None
    assert preferences.location == "Leeds"
    assert preferences.location_label == "Leeds, England, United Kingdom"


def test_location_is_saved_unresolved_when_the_provider_is_down(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeProvider()
    provider.fail = True

    stored = ProfileService(UserRepository(session), provider).replace_preferences(
        user.id, PreferencesUpdateRequest(location="Leeds")
    )

    assert stored.location == "Leeds"
    assert stored.location_label is None


def test_an_unchanged_resolved_location_is_not_geocoded_again(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeProvider()
    _save_location(session, user.id, provider, "Leeds")
    _save_location(session, user.id, provider, "Leeds")

    assert provider.geocode_calls == ["Leeds"]


def test_clearing_the_location_clears_its_resolution(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeProvider()
    _save_location(session, user.id, provider, "Leeds")

    cleared = ProfileService(UserRepository(session), provider).replace_preferences(
        user.id, PreferencesUpdateRequest()
    )

    assert cleared.location is None
    assert cleared.location_label is None
    assert cleared.timezone is None


# --- the forecast -------------------------------------------------------


def test_forecast_requires_a_location(session: Session) -> None:
    user = make_user(session, email="a@example.com")

    with pytest.raises(ApiError) as error:
        _service(session, FakeProvider()).forecast(user.id)

    assert error.value.status_code == 409
    assert error.value.code == "location_required"


def test_forecast_fetches_and_stores_seven_days(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeProvider()
    _save_location(session, user.id, provider, "Leeds")

    forecast = _service(session, provider).forecast(user.id)

    assert forecast.stale is False
    assert forecast.location_label == "Leeds, England, United Kingdom"
    assert forecast.temperature_unit == "fahrenheit"
    assert len(forecast.days) == 7
    assert forecast.days[0].date == date(2026, 9, 26)
    assert forecast.days[0].condition == "clear"
    assert forecast.days[1].condition == "rain"
    assert forecast.days[0].high_celsius == 18.5
    assert session.query(WeatherSnapshot).count() == 7


def test_a_fresh_forecast_is_served_from_the_cache(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeProvider()
    _save_location(session, user.id, provider, "Leeds")
    _service(session, provider).forecast(user.id)

    later = _service(session, provider, NOW + timedelta(minutes=30)).forecast(user.id)

    assert provider.forecast_calls == 1
    assert len(later.days) == 7


def test_an_old_forecast_is_refreshed_in_place(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeProvider()
    _save_location(session, user.id, provider, "Leeds")
    _service(session, provider).forecast(user.id)

    _service(session, provider, NOW + timedelta(hours=2)).forecast(user.id)

    assert provider.forecast_calls == 2
    # Upserted per day, not appended.
    assert session.query(WeatherSnapshot).count() == 7


def test_a_cached_forecast_is_served_stale_when_the_provider_is_down(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeProvider()
    _save_location(session, user.id, provider, "Leeds")
    _service(session, provider).forecast(user.id)
    provider.fail = True

    stale = _service(session, provider, NOW + timedelta(hours=2)).forecast(user.id)

    assert stale.stale is True
    assert len(stale.days) == 7


def test_no_cache_and_no_provider_is_unavailable(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeProvider()
    _save_location(session, user.id, provider, "Leeds")
    provider.fail = True

    with pytest.raises(ApiError) as error:
        _service(session, provider).forecast(user.id)

    assert error.value.status_code == 503
    assert error.value.code == "weather_unavailable"


def test_a_location_saved_while_the_provider_was_down_resolves_later(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeProvider()
    provider.fail = True
    _save_location(session, user.id, provider, "Leeds")
    provider.fail = False

    forecast = _service(session, provider).forecast(user.id)

    assert forecast.location_label == "Leeds, England, United Kingdom"
    preferences = UserRepository(session).get_preferences(user.id)
    assert preferences is not None
    assert preferences.latitude == LEEDS.latitude


def test_a_location_that_never_resolves_is_a_conflict(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeProvider()
    provider.fail = True
    _save_location(session, user.id, provider, "Nowhereville")
    provider.fail = False
    provider.places = []

    with pytest.raises(ApiError) as error:
        _service(session, provider).forecast(user.id)

    assert error.value.status_code == 409
    assert error.value.code == "location_unresolved"


def test_changing_location_does_not_serve_the_old_forecast(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeProvider()
    _save_location(session, user.id, provider, "Leeds")
    _service(session, provider).forecast(user.id)

    provider.places = [
        Place(
            name="Lisbon",
            latitude=Decimal("38.71667"),
            longitude=Decimal("-9.13333"),
            timezone="Europe/Lisbon",
            admin1="Lisbon",
            country="Portugal",
            country_code="PT",
        )
    ]
    _save_location(session, user.id, provider, "Lisbon")
    forecast = _service(session, provider, NOW + timedelta(minutes=5)).forecast(user.id)

    assert provider.forecast_calls == 2
    assert forecast.location_label == "Lisbon, Portugal"
    assert session.query(WeatherSnapshot).count() == 7


def test_today_follows_the_members_timezone(session: Session) -> None:
    user = make_user(session, email="a@example.com")
    provider = FakeProvider(
        [
            Place(
                name="Auckland",
                latitude=Decimal("-36.84853"),
                longitude=Decimal("174.76349"),
                timezone="Pacific/Auckland",
                admin1="Auckland",
                country="New Zealand",
                country_code="NZ",
            )
        ]
    )
    _save_location(session, user.id, provider, "Auckland")

    # 15:00 UTC on the 26th is already the 27th in Auckland, so the provider's
    # first day (the 26th) is in the past and dropped.
    forecast = _service(session, provider).forecast(user.id)

    assert forecast.days[0].date == date(2026, 9, 27)


def test_forecasts_are_private_to_each_member(session: Session) -> None:
    first = make_user(session, email="first@example.com")
    second = make_user(session, email="second@example.com")
    provider = FakeProvider()
    _save_location(session, first.id, provider, "Leeds")
    _service(session, provider).forecast(first.id)

    assert (
        WeatherRepository(session).list_from(
            second.id, date(2026, 9, 26), location_label=LEEDS.label, limit=7
        )
        == []
    )
    with pytest.raises(ApiError) as error:
        _service(session, provider).forecast(second.id)
    assert error.value.code == "location_required"
