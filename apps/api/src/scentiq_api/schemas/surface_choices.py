"""Validated, member-scoped choice browsing contracts."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from scentiq_api.schemas.discovery import DiscoveryMode, DiscoveryResult
from scentiq_api.schemas.enums import Season
from scentiq_api.schemas.layering import LayeringGoal, LayeringStackSuggestion


class DiscoveryChoiceParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: DiscoveryMode = "balance"
    gender: Literal["female", "male", "unisex"] | None = None
    family: str | None = Field(default=None, max_length=100)
    season: Season | None = None
    accord: str | None = Field(default=None, max_length=100)
    minimum_value: float | None = Field(default=None, ge=0, le=5)


class LayeringChoiceParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    anchor_id: UUID | None = None
    mode: Literal["safe", "balanced", "contrast", "experimental"] = "balanced"
    goal: LayeringGoal | None = None


class SurfaceChoiceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    batch_id: UUID | None = None
    idempotency_key: UUID
    reset: bool = False
    advance: bool = True
    expected_candidate_id: str | None = Field(default=None, max_length=120)
    parameters: dict[str, object] = Field(default_factory=dict)


class SurfaceChoiceResponse(BaseModel):
    batch_id: UUID
    selected: DiscoveryResult | LayeringStackSuggestion | None
    candidate_id: str | None
    remaining_options: int
    options_exhausted: bool
