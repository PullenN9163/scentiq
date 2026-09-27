"""Collection endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from scentiq_api.auth import AuthenticatedUser, CurrentUserDependency
from scentiq_api.repositories import CollectionRepository, FragranceRepository
from scentiq_api.schemas import (
    CollectionItemCreateRequest,
    CollectionItemResponse,
    CollectionItemUpdateRequest,
)
from scentiq_api.services import CollectionService


def create_collection_router(
    get_session: object,
    current_user: CurrentUserDependency,
) -> APIRouter:
    router = APIRouter(prefix="/collection", tags=["collection"])

    def _service(session: Session) -> CollectionService:
        return CollectionService(CollectionRepository(session), FragranceRepository(session))

    @router.get("", response_model=list[CollectionItemResponse])
    def list_collection(
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> list[CollectionItemResponse]:
        return _service(session).list_for_user(user.user_id)

    @router.post("", response_model=CollectionItemResponse, status_code=status.HTTP_201_CREATED)
    def add_collection_item(
        payload: CollectionItemCreateRequest,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> CollectionItemResponse:
        created = _service(session).add(user.user_id, payload)
        session.commit()
        return created

    @router.patch("/{item_id}", response_model=CollectionItemResponse)
    def update_collection_item(
        item_id: UUID,
        payload: CollectionItemUpdateRequest,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> CollectionItemResponse:
        updated = _service(session).update(user.user_id, item_id, payload)
        session.commit()
        return updated

    return router
