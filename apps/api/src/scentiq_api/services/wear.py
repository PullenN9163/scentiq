"""Wear logging."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from scentiq_api.errors import not_found, unprocessable
from scentiq_api.models import WearLog
from scentiq_api.repositories import CollectionRepository, WearLogRepository
from scentiq_api.schemas import WearLogCreateRequest, WearLogResponse


class WearLogService:
    def __init__(
        self,
        repository: WearLogRepository,
        collection: CollectionRepository,
    ) -> None:
        self._repository = repository
        self._collection = collection

    def list_for_user(
        self,
        user_id: UUID,
        *,
        collection_item_id: UUID | None = None,
        fragrance_id: UUID | None = None,
        worn_from: datetime | None = None,
        worn_to: datetime | None = None,
        limit: int = 50,
    ) -> list[WearLogResponse]:
        rows = self._repository.list_for_user(
            user_id,
            collection_item_id=collection_item_id,
            fragrance_id=fragrance_id,
            worn_from=worn_from,
            worn_to=worn_to,
            limit=limit,
        )
        return [
            WearLogResponse(
                id=entry.id,
                collection_item_id=entry.collection_item_id,
                fragrance_id=fragrance_id_value,
                fragrance_name=fragrance_name,
                brand_name=brand_name,
                worn_at=entry.worn_at,
                sprays=entry.sprays,
                occasion=entry.occasion,
                setting=entry.setting,
                notes=entry.notes,
            )
            for entry, fragrance_id_value, fragrance_name, brand_name in rows
        ]

    def add(self, user_id: UUID, request: WearLogCreateRequest) -> WearLogResponse:
        # The collection item must belong to the caller; someone else's id is
        # simply not found.
        item = self._collection.get_for_user(user_id, request.collection_item_id)
        if item is None:
            raise not_found("Collection item not found")

        if item.status == "wishlist":
            raise unprocessable(
                "item_not_wearable",
                "A wishlist item cannot have a wear logged against it",
            )

        entry = WearLog(
            user_id=user_id,
            collection_item_id=item.id,
            worn_at=request.worn_at,
            sprays=request.sprays,
            occasion=request.occasion,
            setting=request.setting,
            notes=request.notes,
        )
        created = self._repository.add(entry)
        return WearLogResponse(
            id=created.id,
            collection_item_id=created.collection_item_id,
            fragrance_id=item.fragrance_id,
            fragrance_name=item.fragrance.name,
            brand_name=item.fragrance.brand.name,
            worn_at=created.worn_at,
            sprays=created.sprays,
            occasion=created.occasion,
            setting=created.setting,
            notes=created.notes,
        )
