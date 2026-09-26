from typing import Literal

from pydantic import BaseModel, Field

from scentiq_api.schemas.catalog import FragranceSummary

LayeringMode = Literal["safe", "contrast", "experimental"]


class LayeringSuggestion(BaseModel):
    first: FragranceSummary
    second: FragranceSummary
    mode: LayeringMode
    score: float
    shared_notes: list[str]
    complementary_accords: list[str]
    season_overlap: float = Field(ge=0, le=1)
