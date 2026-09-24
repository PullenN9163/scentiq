"""Collection contracts.

Money crosses the wire as a decimal string so no precision is lost to binary
floating point. Volumes and scores stay numeric.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from scentiq_api.schemas.catalog import FragranceSummary
from scentiq_api.schemas.enums import CollectionStatus, OwnershipType, Projection


class CollectionItemResponse(BaseModel):
    id: UUID
    ownership_type: OwnershipType
    bottle_size_ml: float | None
    remaining_ml: float | None
    # Decimal string, e.g. "129.00"; null when no price was recorded.
    purchase_price: str | None
    purchase_date: date | None
    user_rating: int | None
    custom_longevity: float | None
    custom_projection: Projection | None
    status: CollectionStatus
    fragrance: FragranceSummary


class CollectionItemCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fragrance_id: UUID
    ownership_type: OwnershipType
    bottle_size_ml: Decimal | None = Field(default=None, gt=0, max_digits=7, decimal_places=2)
    remaining_ml: Decimal | None = Field(default=None, ge=0, max_digits=7, decimal_places=2)
    purchase_price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    purchase_date: date | None = None
    user_rating: int | None = Field(default=None, ge=1, le=5)
    custom_longevity: Decimal | None = Field(default=None, ge=0, le=10, decimal_places=1)
    custom_projection: Projection | None = None
    status: CollectionStatus = "owned"

    @field_validator("user_rating")
    @classmethod
    def whole_rating(cls, value: int | None) -> int | None:
        # Declared as int, so this only guards against bool sneaking through.
        if isinstance(value, bool):
            raise ValueError("Rating must be a whole number from 1 to 5")
        return value


class CollectionItemUpdateRequest(BaseModel):
    """Partial update. Every field is optional; omitted fields are untouched.

    `status` is how an item is retired: setting it to `finished` or `sold`
    preserves the wear history that a hard delete would destroy.
    """

    model_config = ConfigDict(extra="forbid")

    ownership_type: OwnershipType | None = None
    bottle_size_ml: Decimal | None = Field(default=None, gt=0, max_digits=7, decimal_places=2)
    remaining_ml: Decimal | None = Field(default=None, ge=0, max_digits=7, decimal_places=2)
    purchase_price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    purchase_date: date | None = None
    user_rating: int | None = Field(default=None, ge=1, le=5)
    custom_longevity: Decimal | None = Field(default=None, ge=0, le=10, decimal_places=1)
    custom_projection: Projection | None = None
    status: CollectionStatus | None = None
