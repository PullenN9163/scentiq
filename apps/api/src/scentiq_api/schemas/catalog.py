from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from scentiq_api.schemas.enums import NoteStage, Occasion, Projection, Season


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
    projection_level: Projection | None
    brand: BrandResponse
    # True for the caller's own private entry, false for a shared curated one.
    is_custom: bool = False


class NoteResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    stage: NoteStage


class AccordResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    weight: float


class SeasonResponse(BaseModel):
    season: Season
    weight: float


class OccasionResponse(BaseModel):
    occasion: Occasion
    weight: float


class FragranceDetail(FragranceSummary):
    description: str | None
    notes: list[NoteResponse]
    accords: list[AccordResponse]
    seasons: list[SeasonResponse]
    occasions: list[OccasionResponse]


class FragranceCreateRequest(BaseModel):
    """A private custom fragrance.

    Brand, name and concentration are required; the descriptive and
    classification metadata a curated entry carries is optional here, and
    insights report what is missing rather than guessing.
    """

    model_config = ConfigDict(extra="forbid")

    brand_name: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=160)
    concentration: str = Field(min_length=1, max_length=40)
    release_year: int | None = Field(default=None, ge=1700, le=2100)
    description: str | None = Field(default=None, max_length=4000)
    longevity_score: float | None = Field(default=None, ge=0, le=10)
    projection_level: Projection | None = None

    @field_validator("brand_name", "name", "concentration")
    @classmethod
    def require_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value must not be blank")
        return stripped

    @field_validator("description")
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
