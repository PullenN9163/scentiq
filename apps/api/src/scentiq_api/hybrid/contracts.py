from __future__ import annotations

from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from scentiq_api.schemas import FragranceSummary


class HybridCollectionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fragrance_id: UUID
    status: str
    user_rating: int | None = Field(default=None, ge=1, le=5)


class HybridPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferred_season: str | None = None
    preferred_occasion: str | None = None
    preferred_projection: str | None = None
    preferred_longevity: float | None = None
    maximum_sprays: int | None = None


class HybridFragrance(BaseModel):
    """Portable scoring features; contains catalog data, never member identity."""

    model_config = ConfigDict(extra="forbid")

    fragrance: FragranceSummary
    accords: dict[str, float] = Field(default_factory=dict)
    notes: dict[str, float] = Field(default_factory=dict)
    seasons: dict[str, float] = Field(default_factory=dict)
    family: str | None = None
    similarities: dict[UUID, float] = Field(default_factory=dict)


class RecommendationJobInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    job_id: UUID
    execution_id: UUID = Field(default_factory=uuid4)
    job_type: Literal["recommendation_bundle"] = "recommendation_bundle"
    input_version: int = Field(ge=0)
    catalog_version: str
    collection: list[HybridCollectionItem]
    preferences: HybridPreferences | None = None
    owned: list[HybridFragrance] = Field(default_factory=list)
    candidates: list[HybridFragrance] = Field(default_factory=list)


class RecommendationJobResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    job_id: UUID
    execution_id: UUID = Field(default_factory=uuid4)
    job_type: Literal["recommendation_bundle"] = "recommendation_bundle"
    input_version: int = Field(ge=0)
    algorithm_version: str
    catalog_version: str
    payload: dict[str, Any]


class JobPointer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    execution_id: UUID | None = None
    input_blob: str


class ResultPointer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    execution_id: UUID | None = None
    output_blob: str


class PoisonMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    execution_id: UUID | None = None
    error_code: str
    dequeue_count: int
