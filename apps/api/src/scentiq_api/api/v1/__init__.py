from collections.abc import Callable, Iterator
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy.orm import Session

from scentiq_api.api.v1.collection import create_collection_router
from scentiq_api.api.v1.fragrances import create_fragrance_router


def create_v1_router(
    get_session: Callable[[], Iterator[Session]],
    demo_user_id: UUID,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    router.include_router(create_fragrance_router(get_session))
    router.include_router(create_collection_router(get_session, demo_user_id))
    return router
