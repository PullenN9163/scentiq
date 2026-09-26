from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from scentiq_api.auth import AuthenticatedUser, CurrentUserDependency
from scentiq_api.repositories import LayeringRepository
from scentiq_api.schemas import LayeringMode, LayeringSuggestion
from scentiq_api.services import LayeringService


def create_layering_router(get_session: object, current_user: CurrentUserDependency) -> APIRouter:
    router = APIRouter(prefix="/layering", tags=["layering"])

    @router.get("/suggestions", response_model=list[LayeringSuggestion])
    def suggestions(
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
        mode: LayeringMode = "safe",
        limit: Annotated[int, Query(ge=1, le=50)] = 12,
        first_id: UUID | None = None,
        second_id: UUID | None = None,
    ) -> list[LayeringSuggestion]:
        return LayeringService(LayeringRepository(session)).suggest(
            user.user_id,
            mode=mode,
            limit=limit,
            first_id=first_id,
            second_id=second_id,
        )

    return router
