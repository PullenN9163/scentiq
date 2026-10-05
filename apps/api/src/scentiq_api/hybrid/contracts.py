from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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


class RecommendationJobInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    job_id: UUID
    job_type: Literal["recommendation_bundle"] = "recommendation_bundle"
    user_id: UUID
    input_version: int = Field(ge=0)
    catalog_version: str
    collection: list[HybridCollectionItem]
    preferences: HybridPreferences | None = None


class RecommendationJobResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    job_id: UUID
    job_type: Literal["recommendation_bundle"] = "recommendation_bundle"
    input_version: int = Field(ge=0)
    algorithm_version: str
    catalog_version: str
    payload: dict[str, Any]


class JobPointer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    input_blob: str


class ResultPointer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    output_blob: str


class PoisonMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    error_code: str
    dequeue_count: int
