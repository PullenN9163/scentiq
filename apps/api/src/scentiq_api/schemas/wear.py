"""Wear-log contracts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from scentiq_api.schemas.enums import Occasion


class WearLogResponse(BaseModel):
    id: UUID
    collection_item_id: UUID
    fragrance_id: UUID
    fragrance_name: str
    brand_name: str
    worn_at: datetime
    sprays: int | None = None
    occasion: Occasion | None = None
    setting: str | None = None
    # The owner's own note text is returned to them; it is the telemetry
    # pipeline, not this contract, that must never carry it.
    notes: str | None = None


class WearLogCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collection_item_id: UUID
    worn_at: datetime
    sprays: int | None = Field(default=None, ge=1, le=30)
    occasion: Occasion | None = None
    setting: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("worn_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("worn_at must include a timezone offset")
        return value

    @field_validator("setting", "notes")
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
