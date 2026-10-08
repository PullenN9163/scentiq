"""Forecast contracts.

Temperatures are always Celsius; `temperature_unit` tells the client which unit
the member wants them shown in.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from scentiq_api.schemas.enums import TemperatureUnit

WeatherConditionValue = Literal[
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


class ForecastDay(BaseModel):
    date: date
    condition: WeatherConditionValue
    high_celsius: float
    low_celsius: float | None = None
    precipitation_probability: float | None = Field(
        default=None, description="0 to 1, the day's highest hourly chance."
    )
    humidity: int | None = Field(default=None, description="Mean relative humidity, 0 to 100.")


class WeatherForecastResponse(BaseModel):
    location_label: str
    timezone: str | None = None
    temperature_unit: TemperatureUnit
    fetched_at: datetime
    stale: bool = Field(
        description="True when the provider was unreachable and a cached forecast is shown."
    )
    days: list[ForecastDay]


class PlaceResponse(BaseModel):
    label: str
    latitude: float
    longitude: float
    timezone: str | None = None
