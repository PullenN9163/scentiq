from collections.abc import Callable, Iterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from scentiq_api.repositories import CollectionRepository
from scentiq_api.schemas import CollectionItemResponse
from scentiq_api.services import CollectionService


def create_collection_router(
    get_session: Callable[[], Iterator[Session]],
    demo_user_id: UUID,
) -> APIRouter:
    router = APIRouter(prefix="/collection", tags=["collection"])

    @router.get("", response_model=list[CollectionItemResponse])
    def list_collection(
        session: Annotated[Session, Depends(get_session)],
    ) -> list[CollectionItemResponse]:
        return CollectionService(CollectionRepository(session)).list_for_user(demo_user_id)

    return router
