from datetime import date
from uuid import UUID

from pydantic import BaseModel

from scentiq_api.schemas.catalog import FragranceSummary


class CollectionItemResponse(BaseModel):
    id: UUID
    user_id: UUID
    ownership_type: str
    bottle_size_ml: float | None
    remaining_ml: float | None
    purchase_price: float | None
    purchase_date: date | None
    user_rating: int | None
    custom_longevity: float | None
    custom_projection: str | None
    status: str
    fragrance: FragranceSummary
