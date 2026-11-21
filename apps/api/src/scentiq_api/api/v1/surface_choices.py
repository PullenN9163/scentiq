"""Authenticated contextual choice browsing."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from scentiq_api.auth import AuthenticatedUser, CurrentUserDependency
from scentiq_api.schemas.surface_choices import SurfaceChoiceRequest, SurfaceChoiceResponse
from scentiq_api.services.surface_choices import SurfaceChoiceService


def create_surface_choices_router(
    get_session: object, current_user: CurrentUserDependency
) -> APIRouter:
    router = APIRouter(prefix="/recommendation-options", tags=["recommendation-options"])

    @router.post("/{surface}", response_model=SurfaceChoiceResponse)
    def choose(
        surface: Literal["discovery", "layering"],
        payload: SurfaceChoiceRequest,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> SurfaceChoiceResponse:
        result = SurfaceChoiceService(session).choose(user.user_id, surface, payload)
        session.commit()
        return result

    return router
