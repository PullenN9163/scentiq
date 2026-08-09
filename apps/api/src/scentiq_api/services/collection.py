from uuid import UUID

from scentiq_api.repositories import CollectionRepository
from scentiq_api.schemas import CollectionItemResponse, FragranceSummary


class CollectionService:
    def __init__(self, repository: CollectionRepository) -> None:
        self._repository = repository

    def list_for_user(self, user_id: UUID) -> list[CollectionItemResponse]:
        return [
            CollectionItemResponse(
                id=item.id,
                user_id=item.user_id,
                ownership_type=item.ownership_type,
                bottle_size_ml=float(item.bottle_size_ml) if item.bottle_size_ml else None,
                remaining_ml=float(item.remaining_ml) if item.remaining_ml is not None else None,
                purchase_price=float(item.purchase_price)
                if item.purchase_price is not None
                else None,
                purchase_date=item.purchase_date,
                user_rating=item.user_rating,
                custom_longevity=(
                    float(item.custom_longevity) if item.custom_longevity is not None else None
                ),
                custom_projection=item.custom_projection,
                status=item.status,
                fragrance=FragranceSummary.model_validate(item.fragrance),
            )
            for item in self._repository.list_for_user(user_id)
        ]
