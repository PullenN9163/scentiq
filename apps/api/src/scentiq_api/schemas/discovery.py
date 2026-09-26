from pydantic import BaseModel, Field

from scentiq_api.schemas.catalog import FragranceSummary


class DiscoveryResult(BaseModel):
    fragrance: FragranceSummary
    taste_match: float = Field(ge=0, le=1)
    collection_expansion: float = Field(ge=0, le=1)
    redundancy_risk: float = Field(ge=0, le=1)
    score: float
