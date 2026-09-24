"""Collection reads and writes, all scoped to the authenticated user."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from scentiq_api.errors import conflict, not_found
from scentiq_api.models import UserCollectionItem
from scentiq_api.repositories import CollectionRepository, FragranceRepository
from scentiq_api.schemas import (
    CollectionItemCreateRequest,
    CollectionItemResponse,
    CollectionItemUpdateRequest,
)
from scentiq_api.services.fragrances import to_fragrance_summary


def _money(value: Decimal | None) -> str | None:
    if value is None:
        return None
    # Fixed-point text, never scientific notation.
    return format(value.quantize(Decimal("0.01")), "f")


def _response(item: UserCollectionItem) -> CollectionItemResponse:
    return CollectionItemResponse(
        id=item.id,
        ownership_type=item.ownership_type,
        bottle_size_ml=float(item.bottle_size_ml) if item.bottle_size_ml is not None else None,
        remaining_ml=float(item.remaining_ml) if item.remaining_ml is not None else None,
        purchase_price=_money(item.purchase_price),
        purchase_date=item.purchase_date,
        user_rating=item.user_rating,
        custom_longevity=(
            float(item.custom_longevity) if item.custom_longevity is not None else None
        ),
        custom_projection=item.custom_projection,
        status=item.status,
        fragrance=to_fragrance_summary(item.fragrance),
    )


class CollectionService:
    def __init__(
        self,
        repository: CollectionRepository,
        fragrances: FragranceRepository,
    ) -> None:
        self._repository = repository
        self._fragrances = fragrances

    def list_for_user(self, user_id: UUID) -> list[CollectionItemResponse]:
        return [_response(item) for item in self._repository.list_for_user(user_id)]

    def get(self, user_id: UUID, item_id: UUID) -> CollectionItemResponse:
        item = self._repository.get_for_user(user_id, item_id)
        if item is None:
            raise not_found("Collection item not found")
        return _response(item)

    def add(
        self,
        user_id: UUID,
        request: CollectionItemCreateRequest,
    ) -> CollectionItemResponse:
        # Visibility check doubles as the ownership check: a private fragrance
        # belonging to another user simply is not found.
        fragrance = self._fragrances.get(user_id, request.fragrance_id)
        if fragrance is None:
            raise not_found("Fragrance not found")

        if self._repository.find_existing(user_id, request.fragrance_id) is not None:
            raise conflict(
                "collection_item_exists",
                "That fragrance is already in your collection",
            )

        item = UserCollectionItem(
            user_id=user_id,
            fragrance_id=request.fragrance_id,
            ownership_type=request.ownership_type,
            bottle_size_ml=request.bottle_size_ml,
            remaining_ml=request.remaining_ml,
            purchase_price=request.purchase_price,
            purchase_date=request.purchase_date,
            user_rating=request.user_rating,
            custom_longevity=request.custom_longevity,
            custom_projection=request.custom_projection,
            status=request.status,
        )
        created = self._repository.add(item)
        created.fragrance = fragrance
        return _response(created)

    def update(
        self,
        user_id: UUID,
        item_id: UUID,
        request: CollectionItemUpdateRequest,
    ) -> CollectionItemResponse:
        item = self._repository.get_for_user(user_id, item_id)
        if item is None:
            raise not_found("Collection item not found")

        # `exclude_unset` is what separates "omitted" from "explicitly null":
        # an omitted field is left alone, an explicit null clears the value.
        changes = request.model_dump(exclude_unset=True)
        if not changes:
            return _response(item)

        updated = self._repository.apply_changes(item, changes)
        return _response(updated)
