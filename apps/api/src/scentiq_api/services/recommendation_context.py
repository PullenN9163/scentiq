"""Shared, timezone-aware context built solely from member-scoped stored inputs."""

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from scentiq_api.models import UserPreference
from scentiq_api.repositories.weather import WeatherRepository
from scentiq_api.services.weather import FORECAST_TTL, _aware, zone_for


def season_for(day: date, latitude: float | None) -> str:
    index = (day.month % 12) // 3
    if latitude is not None and latitude < 0:
        index = (index + 2) % 4
    return ("winter", "spring", "summer", "fall")[index]


class RecommendationContextBuilder:
    def __init__(
        self, session: Session, *, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        self.session, self.clock = session, clock

    def build(
        self,
        user_id: UUID,
        when: datetime,
        *,
        source: str,
        key: str,
        duration_minutes: int | None = None,
    ) -> dict[str, object]:
        if when.tzinfo is None:
            raise ValueError("Recommendation time must include a timezone")
        if duration_minutes is not None and not 1 <= duration_minutes <= 31 * 24 * 60:
            raise ValueError("Event duration must be between one minute and 31 days")
        preferences = self.session.scalar(
            select(UserPreference).where(UserPreference.user_id == user_id)
        )
        zone = zone_for(preferences.timezone if preferences else None)
        local = when.astimezone(zone)
        weather = WeatherRepository(self.session).get_day(user_id, local.date())
        if weather and (not preferences or weather.location_label != preferences.location_label):
            weather = None
        context: dict[str, object] = {
            "duration_minutes": duration_minutes,
            "context_key": key,
            "recommended_for": when,
            "local_date": local.date(),
            "timezone": str(zone),
            "source": source,
            "occasion": preferences.preferred_occasion if preferences else None,
            "daypart": "night" if local.hour >= 18 or local.hour < 6 else "day",
            "season": season_for(
                local.date(),
                float(preferences.latitude)
                if preferences and preferences.latitude is not None
                else None,
            ),
            "weather_resolution": "unavailable",
            "weather_stale": False,
            "high_celsius": None,
            "low_celsius": None,
            "humidity": None,
            "precipitation_probability": None,
            "condition": None,
        }
        if weather is None:
            return context
        if duration_minutes is not None:
            return self._window(user_id, when, duration_minutes, context, weather.location_label)
        fetched = _aware(weather.fetched_at) if weather.fetched_at else None
        context.update(
            {
                "high_celsius": float(weather.temperature_celsius),
                "low_celsius": float(weather.temperature_min_celsius)
                if weather.temperature_min_celsius is not None
                else None,
                "humidity": weather.humidity,
                "precipitation_probability": float(weather.precipitation_probability)
                if weather.precipitation_probability is not None
                else None,
                "condition": weather.condition,
                "weather_fetched_at": fetched,
                "weather_stale": fetched is None or _aware(self.clock()) - fetched >= FORECAST_TTL,
                "weather_resolution": "daily",
            }
        )
        for hour in weather.hourly_forecast or []:
            try:
                at = datetime.fromisoformat(str(hour["at"]))
                if at.tzinfo is None:
                    continue
                if not timedelta() <= when - at < timedelta(hours=1):
                    continue
                context.update(
                    {
                        "high_celsius": hour["temperature_celsius"],
                        "humidity": hour.get("humidity"),
                        "precipitation_probability": hour.get("precipitation_probability"),
                        "condition": hour.get("condition"),
                        "weather_resolution": "hourly",
                    }
                )
                break
            except KeyError, ValueError, TypeError:
                continue
        return context

    def _window(
        self,
        user_id: UUID,
        when: datetime,
        duration: int,
        context: dict[str, object],
        location_label: str,
    ) -> dict[str, object]:
        """Use the most projection-demanding conditions across the entire event."""
        zone = zone_for(str(context["timezone"]))
        start = when.astimezone(UTC)
        end = start + timedelta(minutes=duration)
        hour = start.replace(minute=0, second=0, microsecond=0)
        repository = WeatherRepository(self.session)
        snapshots = {}
        temperatures, lows, humidities, probabilities = [], [], [], []
        conditions, fetched = [], []
        hourly_only = True
        complete = True
        severity = [
            "unknown",
            "clear",
            "partly_cloudy",
            "cloudy",
            "fog",
            "drizzle",
            "rain",
            "snow",
            "thunderstorm",
        ]
        while hour < end:
            day = hour.astimezone(zone).date()
            if day not in snapshots:
                snapshots[day] = repository.get_day(user_id, day)
            snapshot = snapshots[day]
            if snapshot is None or snapshot.location_label != location_label:
                complete, hourly_only = False, False
                hour += timedelta(hours=1)
                continue
            if snapshot.fetched_at is not None:
                fetched.append(_aware(snapshot.fetched_at))
            else:
                complete = False
            point = None
            for candidate in snapshot.hourly_forecast or []:
                try:
                    at = datetime.fromisoformat(str(candidate["at"]))
                    if at.tzinfo is not None and at.astimezone(UTC) == hour:
                        point = candidate
                        break
                except KeyError, TypeError, ValueError:
                    continue
            if point is None:
                hourly_only = False
                point = {
                    "temperature_celsius": snapshot.temperature_celsius,
                    "humidity": snapshot.humidity,
                    "precipitation_probability": snapshot.precipitation_probability,
                    "condition": snapshot.condition,
                }
                if snapshot.temperature_min_celsius is not None:
                    lows.append(float(snapshot.temperature_min_celsius))
            temperature = point.get("temperature_celsius")
            if isinstance(temperature, (int, float, Decimal)):
                temperatures.append(float(temperature))
            humidity = point.get("humidity")
            if isinstance(humidity, (int, float)):
                humidities.append(int(humidity))
            probability = point.get("precipitation_probability")
            if isinstance(probability, (int, float, Decimal)):
                probabilities.append(float(probability))
            condition = point.get("condition")
            if condition in severity:
                conditions.append(str(condition))
            hour += timedelta(hours=1)
        context.update(
            {
                "high_celsius": max(temperatures) if temperatures else None,
                "low_celsius": min(temperatures + lows) if temperatures or lows else None,
                "humidity": max(humidities) if humidities else None,
                "precipitation_probability": max(probabilities) if probabilities else None,
                "condition": max(conditions, key=severity.index) if conditions else None,
                "weather_fetched_at": min(fetched) if fetched else None,
                "weather_stale": not complete
                or not fetched
                or _aware(self.clock()) - min(fetched) >= FORECAST_TTL,
                "weather_resolution": "hourly" if hourly_only else "daily",
            }
        )
        return context
