"""Open-Meteo geocoding and daily forecasts.

Open-Meteo needs no key on its free, non-commercial tier. The commercial tier
uses different hosts plus an `apikey` parameter, so both hosts and the key come
from settings.

Calls are synchronous with a short timeout and no retries: a slow provider must
degrade the weather card, never hold a request thread.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal, Protocol

import httpx

WeatherCondition = Literal[
    "clear",
    "partly_cloudy",
    "cloudy",
    "fog",
    "drizzle",
    "rain",
    "snow",
    "thunderstorm",
    "unknown",
]

DEFAULT_TIMEOUT = httpx.Timeout(5.0)
FORECAST_DAYS = 7
_GEOCODING_CANDIDATES = 10
_DAILY_VARIABLES = (
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_probability_max",
    "relative_humidity_2m_mean",
)

# Common ways people qualify a place that the provider spells differently.
_COUNTRY_ALIASES = {
    "uk": "gb",
    "england": "gb",
    "scotland": "gb",
    "wales": "gb",
    "usa": "us",
    "america": "us",
}


class WeatherProviderError(Exception):
    """The provider could not be reached or returned something unusable."""


@dataclass(frozen=True)
class Place:
    name: str
    latitude: Decimal
    longitude: Decimal
    timezone: str | None
    admin1: str | None
    country: str | None
    country_code: str | None

    @property
    def label(self) -> str:
        parts = [self.name]
        if self.admin1 and self.admin1 != self.name:
            parts.append(self.admin1)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts)


@dataclass(frozen=True)
class DailyForecast:
    day: date
    weather_code: int | None
    temperature_max_celsius: Decimal
    temperature_min_celsius: Decimal | None
    precipitation_probability: Decimal | None
    humidity: int | None


class WeatherProvider(Protocol):
    def geocode(self, query: str) -> list[Place]: ...

    def daily_forecast(
        self,
        latitude: Decimal,
        longitude: Decimal,
        timezone: str | None,
        days: int = FORECAST_DAYS,
    ) -> list[DailyForecast]: ...


def condition_for_code(code: int | None) -> WeatherCondition:
    """Collapse a WMO weather interpretation code into the product's conditions."""
    if code is None:
        return "unknown"
    if code == 0:
        return "clear"
    if code in (1, 2):
        return "partly_cloudy"
    if code == 3:
        return "cloudy"
    if code in (45, 48):
        return "fog"
    if 51 <= code <= 57:
        return "drizzle"
    if 61 <= code <= 67 or 80 <= code <= 82:
        return "rain"
    if 71 <= code <= 77 or code in (85, 86):
        return "snow"
    if 95 <= code <= 99:
        return "thunderstorm"
    return "unknown"


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _matches_qualifier(result: dict[str, Any], qualifier: str) -> bool:
    wanted = qualifier.casefold()
    wanted = _COUNTRY_ALIASES.get(wanted, wanted)
    for key in ("country_code", "country", "admin1", "admin2"):
        candidate = result.get(key)
        if isinstance(candidate, str) and candidate.casefold().startswith(wanted):
            return True
    return False


def _place_from(result: dict[str, Any]) -> Place:
    return Place(
        name=str(result["name"]),
        latitude=Decimal(str(result["latitude"])).quantize(Decimal("0.00001")),
        longitude=Decimal(str(result["longitude"])).quantize(Decimal("0.00001")),
        timezone=result.get("timezone"),
        admin1=result.get("admin1"),
        country=result.get("country"),
        country_code=result.get("country_code"),
    )


class OpenMeteoClient:
    def __init__(
        self,
        *,
        forecast_base_url: str,
        geocoding_base_url: str,
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
    ) -> None:
        self._forecast_base_url = forecast_base_url.rstrip("/")
        self._geocoding_base_url = geocoding_base_url.rstrip("/")
        self._api_key = api_key
        self._transport = transport
        self._timeout = timeout

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        if self._api_key:
            params = {**params, "apikey": self._api_key}
        try:
            with httpx.Client(transport=self._transport, timeout=self._timeout) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            # Never echo the URL: with a commercial key it carries the key.
            raise WeatherProviderError(type(error).__name__) from None
        if not isinstance(payload, dict):
            raise WeatherProviderError("unexpected_payload")
        return payload

    def geocode(self, query: str) -> list[Place]:
        """Places matching `query`, best first.

        The provider matches a bare place name only, so "Manchester, UK" is
        searched as "Manchester" and the rest is used to prefer results in the
        named region or country.
        """
        parts = [part.strip() for part in query.split(",") if part.strip()]
        if not parts:
            return []
        name, qualifiers = parts[0], parts[1:]
        payload = self._get(
            f"{self._geocoding_base_url}/v1/search",
            {
                "name": name,
                "count": _GEOCODING_CANDIDATES,
                "language": "en",
                "format": "json",
            },
        )
        raw_results = payload.get("results") or []
        results = [
            result
            for result in raw_results
            if isinstance(result, dict)
            and result.get("name")
            and result.get("latitude") is not None
            and result.get("longitude") is not None
        ]
        if qualifiers:
            qualified = [
                result
                for result in results
                if all(_matches_qualifier(result, qualifier) for qualifier in qualifiers)
            ]
            # A qualifier that matches nothing is more likely a spelling the
            # provider doesn't know than a wrong place; keep the ranked list.
            results = qualified or results
        return [_place_from(result) for result in results]

    def daily_forecast(
        self,
        latitude: Decimal,
        longitude: Decimal,
        timezone: str | None,
        days: int = FORECAST_DAYS,
    ) -> list[DailyForecast]:
        payload = self._get(
            f"{self._forecast_base_url}/v1/forecast",
            {
                "latitude": str(latitude),
                "longitude": str(longitude),
                "daily": ",".join(_DAILY_VARIABLES),
                "timezone": timezone or "auto",
                "forecast_days": days,
                "temperature_unit": "celsius",
            },
        )
        daily = payload.get("daily")
        if not isinstance(daily, dict) or not isinstance(daily.get("time"), list):
            raise WeatherProviderError("unexpected_payload")

        def column(name: str) -> list[Any]:
            values = daily.get(name)
            return values if isinstance(values, list) else [None] * len(daily["time"])

        forecasts: list[DailyForecast] = []
        try:
            for index, day in enumerate(daily["time"]):
                high = _decimal(column("temperature_2m_max")[index])
                if high is None:
                    # A day without a high is not worth showing or planning around.
                    continue
                code = column("weather_code")[index]
                probability = column("precipitation_probability_max")[index]
                humidity = column("relative_humidity_2m_mean")[index]
                forecasts.append(
                    DailyForecast(
                        day=date.fromisoformat(str(day)),
                        weather_code=int(code) if code is not None else None,
                        temperature_max_celsius=high,
                        temperature_min_celsius=_decimal(column("temperature_2m_min")[index]),
                        precipitation_probability=(
                            (Decimal(str(probability)) / 100).quantize(Decimal("0.001"))
                            if probability is not None
                            else None
                        ),
                        humidity=round(humidity) if humidity is not None else None,
                    )
                )
        except IndexError, TypeError, ValueError:
            raise WeatherProviderError("unexpected_payload") from None
        return forecasts
