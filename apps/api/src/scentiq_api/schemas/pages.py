from pydantic import BaseModel, Field

from scentiq_api.schemas.catalog import (
    CommunityResponse,
    FragranceDetail,
    FragranceSummary,
    OccasionResponse,
    SeasonResponse,
)
from scentiq_api.schemas.collection import CollectionItemResponse
from scentiq_api.schemas.identity import MeResponse
from scentiq_api.schemas.insights import CollectionInsightsResponse
from scentiq_api.schemas.recommendations import RecommendationBundleResponse
from scentiq_api.schemas.wear import WearLogResponse


class DashboardPageResponse(BaseModel):
    me: MeResponse
    insights: CollectionInsightsResponse
    recent_wears: list[WearLogResponse]


class LayeringPageResponse(BaseModel):
    collection: list[CollectionItemResponse]
    recommendations: RecommendationBundleResponse


class WeekFragrance(FragranceSummary):
    seasons: list[SeasonResponse] = Field(default_factory=list)
    occasions: list[OccasionResponse] = Field(default_factory=list)
    community: CommunityResponse | None = None


class WeekPageResponse(BaseModel):
    me: MeResponse
    owned: list[WeekFragrance]


class FragrancePageResponse(BaseModel):
    fragrance: FragranceDetail
    collection_item: CollectionItemResponse | None = None
    recent_wears: list[WearLogResponse] = Field(default_factory=list)
