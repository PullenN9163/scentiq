"""Location resolution and cached daily forecasts."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from scentiq_api.errors import ApiError, FieldError, conflict, service_unavailable, unprocessable
from scentiq_api.integrations.weather import (
    WeatherProvider,
    WeatherProviderError,
    condition_for_code,
)
from scentiq_api.integrations.weather.open_meteo import FORECAST_DAYS, Place
from scentiq_api.models import UserPreference, WeatherSnapshot
from scentiq_api.repositories import UserRepository, WeatherRepository
from scentiq_api.repositories.weather import day_key
from scentiq_api.schemas import ForecastDay, PlaceResponse, WeatherForecastResponse

# How long a fetched forecast is served before the provider is asked again.
FORECAST_TTL = timedelta(minutes=60)
WEATHER_SOURCE = "open-meteo"
DEFAULT_TEMPERATURE_UNIT = "fahrenheit"
MAX_PLACE_RESULTS = 5


def location_not_found() -> ApiError:
    return unprocessable(
        "location_not_found",
        "We couldn't find that location",
        [
            FieldError(
                field="location",
                code="location_not_found",
                message='We couldn\'t find that place. Try a city name, e.g. "Leeds, UK".',
            )
        ],
    )


def weather_unavailable() -> ApiError:
    return service_unavailable(
        "weather_unavailable", "The weather service is unavailable right now"
    )


def resolve_place(provider: WeatherProvider, query: str) -> Place | None:
    """The best match for `query`, or None when nothing matches.

    Provider failures propagate so the caller can decide whether to save the
    location unresolved or refuse the request.
    """
    places = provider.geocode(query)
    return places[0] if places else None


def zone_for(timezone: str | None) -> ZoneInfo:
    if timezone:
        try:
            return ZoneInfo(timezone)
        except ZoneInfoNotFoundError, ValueError:
            pass
    return ZoneInfo("UTC")


class WeatherService:
    def __init__(
        self,
        users: UserRepository,
        weather: WeatherRepository,
        provider: WeatherProvider,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._users = users
        self._weather = weather
        self._provider = provider
        self._clock = clock

    def search_places(self, query: str) -> list[PlaceResponse]:
        try:
            places = self._provider.geocode(query)
        except WeatherProviderError:
            raise weather_unavailable() from None
        return [
            PlaceResponse(
                label=place.label,
                latitude=float(place.latitude),
                longitude=float(place.longitude),
                timezone=place.timezone,
            )
            for place in places[:MAX_PLACE_RESULTS]
        ]

    def forecast(self, user_id: UUID) -> WeatherForecastResponse:
        preferences = self._users.get_preferences(user_id)
        if preferences is None or preferences.location is None:
            raise conflict("location_required", "Add a location in Settings to see the forecast")

        label = self._ensure_resolved(preferences)
        now = self._clock()
        today = now.astimezone(zone_for(preferences.timezone)).date()
        unit = preferences.temperature_unit or DEFAULT_TEMPERATURE_UNIT

        cached = self._weather.list_from(user_id, today, location_label=label, limit=FORECAST_DAYS)
        if self._is_fresh(cached, today, now):
            return self._response(preferences, label, unit, cached, stale=False)

        try:
            assert preferences.latitude is not None and preferences.longitude is not None
            forecasts = self._provider.daily_forecast(
                preferences.latitude,
                preferences.longitude,
                preferences.timezone,
            )
        except WeatherProviderError:
            if cached:
                return self._response(preferences, label, unit, cached, stale=True)
            raise weather_unavailable() from None

        stored = [
            self._weather.upsert(
                WeatherSnapshot(
                    user_id=user_id,
                    location_label=label,
                    forecast_at=day_key(forecast.day),
                    temperature_celsius=forecast.temperature_max_celsius,
                    temperature_min_celsius=forecast.temperature_min_celsius,
                    humidity=forecast.humidity,
                    precipitation_probability=forecast.precipitation_probability,
                    weather_code=forecast.weather_code,
                    condition=condition_for_code(forecast.weather_code),
                    source=WEATHER_SOURCE,
                    fetched_at=now,
                )
            )
            for forecast in forecasts
            if forecast.day >= today
        ]
        if not stored:
            raise weather_unavailable()
        return self._response(preferences, label, unit, stored, stale=False)

    def _ensure_resolved(self, preferences: UserPreference) -> str:
        """Resolve a location saved while the provider was unreachable."""
        if (
            preferences.location_label is not None
            and preferences.latitude is not None
            and preferences.longitude is not None
        ):
            return preferences.location_label

        assert preferences.location is not None
        try:
            place = resolve_place(self._provider, preferences.location)
        except WeatherProviderError:
            raise weather_unavailable() from None
        if place is None:
            raise conflict(
                "location_unresolved",
                "We couldn't find your saved location. Update it in Settings.",
            )
        self._users.set_resolved_location(
            preferences,
            label=place.label,
            latitude=place.latitude,
            longitude=place.longitude,
            timezone=place.timezone,
        )
        return place.label

    @staticmethod
    def _is_fresh(cached: list[WeatherSnapshot], today: date, now: datetime) -> bool:
        if not cached or _day_of(cached[0]) != today:
            return False
        fetched = [snapshot.fetched_at for snapshot in cached]
        if any(value is None for value in fetched):
            return False
        oldest = min(_aware(value) for value in fetched if value is not None)
        return now - oldest < FORECAST_TTL

    @staticmethod
    def _response(
        preferences: UserPreference,
        label: str,
        unit: str,
        snapshots: list[WeatherSnapshot],
        *,
        stale: bool,
    ) -> WeatherForecastResponse:
        fetched = [
            _aware(snapshot.fetched_at) for snapshot in snapshots if snapshot.fetched_at is not None
        ]
        return WeatherForecastResponse(
            location_label=label,
            timezone=preferences.timezone,
            temperature_unit="celsius" if unit == "celsius" else "fahrenheit",
            fetched_at=min(fetched) if fetched else datetime.now(UTC),
            stale=stale,
            days=[
                ForecastDay(
                    date=_day_of(snapshot),
                    condition=condition_for_code(snapshot.weather_code),
                    high_celsius=float(snapshot.temperature_celsius),
                    low_celsius=(
                        float(snapshot.temperature_min_celsius)
                        if snapshot.temperature_min_celsius is not None
                        else None
                    ),
                    precipitation_probability=(
                        float(snapshot.precipitation_probability)
                        if snapshot.precipitation_probability is not None
                        else None
                    ),
                    humidity=snapshot.humidity,
                )
                for snapshot in snapshots
            ],
        )


def _aware(value: datetime) -> datetime:
    """SQLite drops the offset on read; every stored timestamp is UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _day_of(snapshot: WeatherSnapshot) -> date:
    """The forecast's calendar date, whatever timezone the connection reads in."""
    return _aware(snapshot.forecast_at).astimezone(UTC).date()
