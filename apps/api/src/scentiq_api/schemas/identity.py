"""Profile, preference and account-deletion contracts.

Identity always comes from the verified token, so no request here carries a
user id.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from scentiq_api.schemas.enums import LifecycleState, Occasion, Projection, Season


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class PreferencesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    location: str | None = None
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


class PreferencesUpdateRequest(BaseModel):
    """A full replacement of the preference set; omitted fields clear."""

    model_config = ConfigDict(extra="forbid")

    location: str | None = Field(default=None, max_length=120)
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
