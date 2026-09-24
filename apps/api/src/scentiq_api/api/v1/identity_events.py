"""Internal identity-event endpoint.

The Next.js webhook route verifies the provider's signature, normalises the
event, and forwards it here with a dedicated service credential. This endpoint
never sees a provider signature and never trusts a user session token.
"""

from collections.abc import Callable
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from scentiq_api.repositories import IdentityRepository
from scentiq_api.services import IdentityEventService


class IdentityEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Provider event id, used to make replays no-ops.
    event_id: str = Field(min_length=1, max_length=255)
    event_type: Literal["user.deleted"]
    subject: str = Field(min_length=1, max_length=255)


class IdentityEventResult(BaseModel):
    event_id: str
    applied: bool


def create_identity_event_router(
    get_session: object,
    require_service_token: Callable[..., None],
) -> APIRouter:
    router = APIRouter(prefix="/internal/identity-events", tags=["internal"])

    @router.post(
        "",
        response_model=IdentityEventResult,
        status_code=status.HTTP_200_OK,
        dependencies=[Depends(require_service_token)],
        include_in_schema=False,
    )
    def receive_identity_event(
        payload: IdentityEventRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> IdentityEventResult:
        service = IdentityEventService(IdentityRepository(session))
        applied = service.handle_user_deleted(
            event_id=payload.event_id,
            subject=payload.subject,
        )
        session.commit()
        # 200 either way: a replay is a successful no-op, so the provider stops
        # retrying instead of escalating.
        return IdentityEventResult(event_id=payload.event_id, applied=applied)

    return router
