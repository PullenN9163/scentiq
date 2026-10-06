from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from scentiq_api.schemas.discovery import DiscoveryResult
from scentiq_api.schemas.layering import LayeringSuggestion


class LayeringRecommendationPayload(BaseModel):
    safe: list[LayeringSuggestion] = Field(default_factory=list)
    contrast: list[LayeringSuggestion] = Field(default_factory=list)
    experimental: list[LayeringSuggestion] = Field(default_factory=list)


class RecommendationPayload(BaseModel):
    discovery: list[DiscoveryResult] = Field(default_factory=list)
    layering: LayeringRecommendationPayload


class RecommendationBundleResponse(BaseModel):
    payload: RecommendationPayload
    input_version: int
    generated_at: datetime | None = None
    is_stale: bool
    refresh_status: Literal["fresh", "pending", "fallback"]
