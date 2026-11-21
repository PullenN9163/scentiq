from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from scentiq_api.auth import AuthenticatedUser, CurrentUserDependency
from scentiq_api.schemas.events import InteractionEventBatch, InteractionEventResult
from scentiq_api.services.events import EventService


def create_events_router(get_session: object, current_user: CurrentUserDependency) -> APIRouter:
    router = APIRouter(prefix="/events", tags=["events"])

    @router.post("", response_model=InteractionEventResult, status_code=202)
    def record_events(
        batch: InteractionEventBatch,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> InteractionEventResult:
        return EventService(session).record(user.user_id, batch)

    return router
