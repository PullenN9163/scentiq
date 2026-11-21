"""Profile, preference and account-deletion contracts.

Identity always comes from the verified token, so no request here carries a
user id.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from scentiq_api.schemas.enums import (
    LifecycleState,
    Occasion,
    Projection,
    Season,
    TemperatureUnit,
)


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class TastePreferences(BaseModel):
    liked_notes: list[str] = Field(default_factory=list, max_length=50)
    disliked_notes: list[str] = Field(default_factory=list, max_length=50)
    liked_accords: list[str] = Field(default_factory=list, max_length=50)
    disliked_accords: list[str] = Field(default_factory=list, max_length=50)
    liked_families: list[str] = Field(default_factory=list, max_length=50)
    disliked_families: list[str] = Field(default_factory=list, max_length=50)
    excluded_fragrance_ids: list[str] = Field(default_factory=list, max_length=500)
    variety_preference: Literal["familiar", "balanced", "adventurous"] = "balanced"
    calendar_ai_titles_enabled: bool = False

    @field_validator(
        "liked_notes",
        "disliked_notes",
        "liked_accords",
        "disliked_accords",
        "liked_families",
        "disliked_families",
    )
    @classmethod
    def normalize_taste(cls, values: list[str]) -> list[str]:
        normalized = sorted({re.sub(r"[\s_]+", "-", value.strip().casefold()) for value in values})
        if any(not value or len(value) > 80 for value in normalized):
            raise ValueError("Taste entries must contain 1 to 80 characters")
        return normalized

    @field_validator("excluded_fragrance_ids")
    @classmethod
    def validate_exclusions(cls, values: list[str]) -> list[str]:
        return sorted({str(UUID(value)) for value in values})

    @model_validator(mode="after")
    def distinct_preferences(self) -> TastePreferences:
        for kind in ("notes", "accords", "families"):
            if set(getattr(self, f"liked_{kind}")) & set(getattr(self, f"disliked_{kind}")):
                raise ValueError(f"The same {kind} cannot be both liked and disliked")
        return self


class PreferencesResponse(TastePreferences):
    model_config = ConfigDict(from_attributes=True)

    location: str | None = None
    location_label: str | None = Field(
        default=None,
        description="The place `location` resolved to; null when unresolved.",
    )
    timezone: str | None = None
    temperature_unit: TemperatureUnit | None = None
    preferred_season: Season | None = None
    preferred_occasion: Occasion | None = None
    preferred_projection: Projection | None = None
    preferred_longevity: float | None = None
    maximum_sprays: int | None = None


class MeResponse(BaseModel):
    id: str
    email: str
    display_name: str
    lifecycle_state: LifecycleState
    created_at: datetime
    preferences: PreferencesResponse


class MeUpdateRequest(BaseModel):
    """Only the display name is writable; email is owned by the provider."""

    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=120)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Display name must not be blank")
        return stripped


class PreferencesUpdateRequest(TastePreferences):
    """A full replacement of the preference set; omitted fields clear."""

    model_config = ConfigDict(extra="forbid")

    location: str | None = Field(default=None, max_length=120)
    temperature_unit: TemperatureUnit | None = None
    preferred_season: Season | None = None
    preferred_occasion: Occasion | None = None
    preferred_projection: Projection | None = None
    preferred_longevity: float | None = Field(default=None, ge=0, le=10)
    maximum_sprays: int | None = Field(default=None, ge=1, le=20)

    @field_validator("location")
    @classmethod
    def normalize_location(cls, value: str | None) -> str | None:
        return _blank_to_none(value)


class DeletionResponse(BaseModel):
    lifecycle_state: LifecycleState
    deletion_requested_at: datetime
