"""Persisted wear recommendation contracts; identity is always server-derived."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from scentiq_api.schemas.catalog import FragranceSummary
from scentiq_api.schemas.enums import Occasion, Season


class RecommendationContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context_key: str
    recommended_for: datetime
    calendar_event_id: UUID | None = None
    local_date: date
    timezone: str
    occasion: Occasion | None = None
    formality: str | None = None
    setting: str | None = None
    daypart: Literal["day", "night"]
    season: Season
    high_celsius: float | None = None
    low_celsius: float | None = None
    humidity: int | None = None
    precipitation_probability: float | None = None
    condition: str | None = None
    source: Literal["today", "day", "event", "manual", "agent"]
    weather_resolution: Literal["hourly", "daily", "unavailable"] = "unavailable"
    weather_stale: bool = False
    weather_fetched_at: datetime | None = None
    duration_minutes: int | None = None


class RecommendationPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    recommended_for: datetime | None = None
    occasion: Occasion | None = None
    setting: str | None = Field(default=None, max_length=40)
    formality: Literal["casual", "smart", "formal"] | None = None
    daypart: Literal["day", "night"] | None = None
    high_celsius: float | None = Field(default=None, ge=-60, le=60)
    low_celsius: float | None = Field(default=None, ge=-60, le=60)
    source: Literal["manual", "agent"] = "manual"

    @field_validator("recommended_for")
    @classmethod
    def aware_date(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("recommended_for must include a timezone")
        return value


DecisionAction = Literal["accepted", "rejected", "replaced", "dismissed"]


class RecommendationDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: DecisionAction
    selected_fragrance_id: UUID | None = None


class RecommendationDecisionResponse(BaseModel):
    action: DecisionAction
    selected_fragrance_id: UUID | None = None


class RecommendationWearRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected_fragrance_id: UUID | None = None
    worn_at: datetime | None = None
    sprays: int | None = Field(default=None, ge=1, le=30)
    occasion: Occasion | None = None
    setting: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("worn_at")
    @classmethod
    def aware_date(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("worn_at must include a timezone")
        return value


class WearRecommendationCandidate(BaseModel):
    fragrance: FragranceSummary
    score: float
    evidence_coverage: float
    recommended_sprays: int
    score_components: dict[str, float]
    reasons: list[str]
    warnings: list[str]


class WearRecommendationResponse(WearRecommendationCandidate):
    id: UUID
    context_key: str
    recommended_for: datetime
    context: RecommendationContext
    algorithm_version: str
    alternatives: list[WearRecommendationCandidate]
    decision: RecommendationDecisionResponse | None = None
    canonical_fragrance_id: UUID | None = None
    generation_mode: str = "baseline"
    model_version: str | None = None
    profile_version: str | None = None
    remaining_options: int = 0
    options_exhausted: bool = False


class WearRecommendationPlan(BaseModel):
    timezone: str
    local_date: date
    recommendations: list[WearRecommendationResponse]
    gaps: list[str]


class RecommendationNextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: UUID
    expected_fragrance_id: UUID | None = None
    reset: bool = False


class RecommendationFeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fragrance_id: UUID
    reason: Literal["not_today", "too_strong", "dislike_scent"]


class RecommendationFeedbackResponse(BaseModel):
    id: UUID
    reason: Literal["not_today", "too_strong", "dislike_scent"]
