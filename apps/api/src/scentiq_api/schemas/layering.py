from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from scentiq_api.schemas.catalog import FragranceSummary

LayeringMode = Literal["safe", "balanced", "contrast", "experimental"]
LayeringGoal = Literal[
    "fresher",
    "warmer",
    "sweeter",
    "darker",
    "cleaner",
    "softer",
    "more_projection",
    "more_intimate",
    "daytime",
    "evening",
    "spring",
    "summer",
    "fall",
    "winter",
]
LayeringRole = Literal["anchor", "bridge", "accent"]


class LayeringSuggestion(BaseModel):
    first: FragranceSummary
    second: FragranceSummary
    mode: LayeringMode
    score: float
    shared_notes: list[str]
    complementary_accords: list[str]
    season_overlap: float = Field(ge=0, le=1)


class LayeringStackItem(BaseModel):
    fragrance: FragranceSummary
    role: LayeringRole
    application_order: int = Field(ge=1, le=3)
    suggested_sprays: int = Field(ge=1, le=6)


class LayeringScoreComponents(BaseModel):
    bridge: float
    complement: float
    season_context: float
    projection_balance: float
    longevity_balance: float
    novelty: float
    user_affinity: float
    redundancy_penalty: float
    overload_penalty: float


class LayeringStackSuggestion(BaseModel):
    items: list[LayeringStackItem]
    mode: LayeringMode
    goal: LayeringGoal | None = None
    score: float = Field(ge=0, le=1)
    score_components: LayeringScoreComponents
    shared_notes: list[str]
    shared_accords: list[str]
    bridge_signals: list[str]
    complementary_signals: list[str]
    best_contexts: list[str]
    reasons: list[str]
    warnings: list[str]
    total_sprays: int
    evidence_coverage: float = Field(ge=0, le=1)
    algorithm_version: str = "layering-v2"
    evidence_label: Literal["limited", "partial", "strong"]


class LayeringStackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fragrance_ids: list[UUID] = Field(min_length=2, max_length=3)
    mode: LayeringMode = "balanced"
    goal: LayeringGoal | None = None

    @model_validator(mode="after")
    def distinct_items(self) -> LayeringStackRequest:
        if len(set(self.fragrance_ids)) != len(self.fragrance_ids):
            raise ValueError("Choose distinct fragrances")
        return self


class LayeringStackSaveRequest(LayeringStackRequest):
    name: str = Field(min_length=1, max_length=120)
    notes: str | None = Field(default=None, max_length=2000)


class LayeringStackRenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)


class LayeringStackWearRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    worn_at: datetime | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = Field(default=None, max_length=2000)


class LayeringStackRatingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rating: int = Field(ge=1, le=5)


class LayeringStackWearResponse(BaseModel):
    id: UUID
    stack_id: UUID
    worn_at: datetime
    rating: int | None
    notes: str | None


class SavedLayeringStack(BaseModel):
    id: UUID
    name: str
    notes: str | None
    created_at: datetime
    last_worn_at: datetime | None
    average_rating: float | None
    wear_count: int
    suggestion: LayeringStackSuggestion


class LayeringIntelligencePage(BaseModel):
    supported_goals: list[LayeringGoal]
    suggestions: list[LayeringStackSuggestion]
    saved: list[SavedLayeringStack]
