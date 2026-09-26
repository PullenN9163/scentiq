"""Calendar connection and event contracts.

Provider tokens never appear here: they stay encrypted in the service.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from scentiq_api.schemas.enums import Occasion

CalendarProviderValue = Literal["google", "microsoft"]
ConnectionStatus = Literal["active", "reauth_required"]
Formality = Literal["formal", "smart", "casual"]


class CalendarProviderStatus(BaseModel):
    provider: CalendarProviderValue
    available: bool = Field(description="False when the provider is not configured here.")


class CalendarSourceResponse(BaseModel):
    id: UUID
    name: str
    color: str | None = None
    is_primary: bool
    is_selected: bool


class CalendarConnectionResponse(BaseModel):
    id: UUID
    provider: CalendarProviderValue
    account_email: str
    status: ConnectionStatus
    last_synced_at: datetime | None = None
    last_error_code: str | None = None
    sources: list[CalendarSourceResponse]


class AuthorizationResponse(BaseModel):
    authorization_url: str


class OAuthCallbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=2048)
    state: str = Field(min_length=16, max_length=256)


class CalendarSourceUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_selected: bool


class CalendarEventResponse(BaseModel):
    id: UUID
    title: str
    starts_at: datetime
    ends_at: datetime
    is_all_day: bool = Field(
        description="All-day events start and end at midnight UTC of their dates; "
        "the end date is exclusive."
    )
    location_label: str | None = None
    occasion: Occasion
    formality: Formality | None = None
    is_hidden: bool
    calendar_name: str | None = None
    provider: CalendarProviderValue | None = None


class CalendarEventUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_hidden: bool
