"""Authenticated wear intelligence, separate from discovery/layering snapshots."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from scentiq_api.auth import AuthenticatedUser, CurrentUserDependency
from scentiq_api.schemas.wear import WearLogResponse
from scentiq_api.schemas.wear_recommendations import (
    RecommendationDecisionRequest,
    RecommendationDecisionResponse,
    RecommendationPreviewRequest,
    RecommendationWearRequest,
    WearRecommendationPlan,
    WearRecommendationResponse,
)
from scentiq_api.services.wear_recommendations import WearRecommendationService


def create_wear_recommendations_router(
    get_session: object,
    current_user: CurrentUserDependency,
    refresh_context: Callable[[Session, UUID], None] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/recommendations", tags=["wear-recommendations"])

    @router.get("/today", response_model=WearRecommendationPlan)
    def today(
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> WearRecommendationPlan:
        if refresh_context:
            refresh_context(session, user.user_id)
        result = WearRecommendationService(session).today(user.user_id)
        session.commit()
        return result

    @router.get("/week", response_model=WearRecommendationPlan)
    def week(
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> WearRecommendationPlan:
        if refresh_context:
            refresh_context(session, user.user_id)
        result = WearRecommendationService(session).week(user.user_id)
        session.commit()
        return result

    @router.post("/preview", response_model=WearRecommendationResponse)
    def preview(
        payload: RecommendationPreviewRequest,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> WearRecommendationResponse:
        if refresh_context:
            refresh_context(session, user.user_id)
        result = WearRecommendationService(session).preview(user.user_id, payload)
        session.commit()
        return result

    @router.post("/{recommendation_id}/decision", response_model=RecommendationDecisionResponse)
    def decision(
        recommendation_id: UUID,
        payload: RecommendationDecisionRequest,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> RecommendationDecisionResponse:
        result = WearRecommendationService(session).decide(user.user_id, recommendation_id, payload)
        session.commit()
        return result

    @router.post("/{recommendation_id}/wear", response_model=WearLogResponse)
    def wear(
        recommendation_id: UUID,
        payload: RecommendationWearRequest,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> WearLogResponse:
        result = WearRecommendationService(session).wear(user.user_id, recommendation_id, payload)
        session.commit()
        return result

    return router
