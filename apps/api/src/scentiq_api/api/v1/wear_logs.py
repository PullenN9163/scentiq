"""Wear-log endpoints."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from scentiq_api.auth import AuthenticatedUser, CurrentUserDependency
from scentiq_api.errors import unprocessable
from scentiq_api.repositories import CollectionRepository, WearLogRepository
from scentiq_api.repositories.wear import MAX_WEAR_LOG_LIMIT
from scentiq_api.schemas import WearLogCreateRequest, WearLogResponse
from scentiq_api.services import WearLogService


def create_wear_log_router(
    get_session: object,
    current_user: CurrentUserDependency,
) -> APIRouter:
    router = APIRouter(prefix="/wear-logs", tags=["wear-logs"])

    def _service(session: Session) -> WearLogService:
        return WearLogService(WearLogRepository(session), CollectionRepository(session))

    @router.get("", response_model=list[WearLogResponse])
    def list_wear_logs(
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
        collection_item_id: UUID | None = None,
        fragrance_id: UUID | None = None,
        worn_from: datetime | None = None,
        worn_to: datetime | None = None,
        limit: Annotated[int, Query(ge=1, le=MAX_WEAR_LOG_LIMIT)] = 50,
    ) -> list[WearLogResponse]:
        if worn_from is not None and worn_to is not None and worn_from > worn_to:
            raise unprocessable(
                "invalid_date_range",
                "worn_from must not be later than worn_to",
            )
        return _service(session).list_for_user(
            user.user_id,
            collection_item_id=collection_item_id,
            fragrance_id=fragrance_id,
            worn_from=worn_from,
            worn_to=worn_to,
            limit=limit,
        )

    @router.post("", response_model=WearLogResponse, status_code=status.HTTP_201_CREATED)
    def add_wear_log(
        payload: WearLogCreateRequest,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> WearLogResponse:
        created = _service(session).add(user.user_id, payload)
        session.commit()
        return created

    return router
