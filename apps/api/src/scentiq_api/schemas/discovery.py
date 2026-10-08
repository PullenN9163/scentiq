from typing import Literal

from pydantic import BaseModel, Field

from scentiq_api.schemas.catalog import FragranceSummary

DiscoveryMode = Literal["balance", "taste", "explore", "seasonal"]


class DiscoveryResult(BaseModel):
    fragrance: FragranceSummary
    taste_match: float = Field(ge=0, le=1)
    collection_expansion: float = Field(ge=0, le=1)
    redundancy_risk: float = Field(ge=0, le=1)
    score: float
    mode: DiscoveryMode = "balance"
    season_fit: float | None = None
    evidence_coverage: float = Field(default=0, ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)
