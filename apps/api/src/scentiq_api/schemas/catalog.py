from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BrandResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str


class FragranceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    concentration: str
    release_year: int | None
    image_blob_path: str | None
    longevity_score: float | None
    projection_level: str | None
    brand: BrandResponse


class NoteResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    stage: str


class AccordResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    weight: float


class SeasonResponse(BaseModel):
    season: str
    weight: float


class OccasionResponse(BaseModel):
    occasion: str
    weight: float


class FragranceDetail(FragranceSummary):
    description: str | None
    notes: list[NoteResponse]
    accords: list[AccordResponse]
    seasons: list[SeasonResponse]
    occasions: list[OccasionResponse]
