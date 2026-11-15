"""Authenticated wear intelligence, separate from discovery/layering snapshots."""

from collections.abc import Callable
from datetime import UTC, datetime
from threading import Lock
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from scentiq_api.auth import AuthenticatedUser, CurrentUserDependency
from scentiq_api.repositories import HybridJobRepository
from scentiq_api.schemas.wear import WearLogResponse
from scentiq_api.schemas.wear_recommendations import (
    RecommendationDecisionRequest,
    RecommendationDecisionResponse,
    RecommendationFeedbackRequest,
    RecommendationFeedbackResponse,
    RecommendationNextRequest,
    RecommendationPreviewRequest,
    RecommendationWearRequest,
    WearRecommendationPlan,
    WearRecommendationResponse,
)
from scentiq_api.services import HybridJobService
from scentiq_api.services.recommendation_choices import RecommendationChoiceService
from scentiq_api.services.ttl_cache import TtlLruCache
from scentiq_api.services.wear_recommendations import WearRecommendationService

# Scoring a week of contexts takes several seconds, the plan changes slowly, and Today shows
# it as a glance, so it is kept briefly. Any recommendation action by the member bumps their
# epoch, which makes their earlier entries unreachable at once. Today's pick is never cached.
_WEEK_CACHE: TtlLruCache[WearRecommendationPlan] = TtlLruCache(max_entries=64, ttl_seconds=120)
_EPOCHS: dict[UUID, int] = {}
_EPOCH_LOCK = Lock()


def _epoch(user_id: UUID) -> int:
    with _EPOCH_LOCK:
        return _EPOCHS.get(user_id, 0)


def _bump_epoch(user_id: UUID) -> None:
    with _EPOCH_LOCK:
        if len(_EPOCHS) > 10_000:
            _EPOCHS.clear()
        _EPOCHS[user_id] = _EPOCHS.get(user_id, 0) + 1


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
        version = HybridJobService(HybridJobRepository(session)).current_input_version(user.user_id)
        key = (
            user.user_id,
            _epoch(user.user_id),
            datetime.now(UTC).strftime("%Y-%m-%dT%H"),
            version,
        )
        cached = _WEEK_CACHE.get(key)
        if cached is not None:
            return cached
        if refresh_context:
            refresh_context(session, user.user_id)
        result = WearRecommendationService(session).week(user.user_id)
        session.commit()
        _WEEK_CACHE.put(key, result)
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
        _bump_epoch(user.user_id)
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
        _bump_epoch(user.user_id)
        return result

    @router.post("/{recommendation_id}/next", response_model=WearRecommendationResponse)
    def next_option(
        recommendation_id: UUID,
        payload: RecommendationNextRequest,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> WearRecommendationResponse:
        result = RecommendationChoiceService(session).next(user.user_id, recommendation_id, payload)
        session.commit()
        _bump_epoch(user.user_id)
        return result

    @router.post("/{recommendation_id}/feedback", response_model=RecommendationFeedbackResponse)
    def feedback(
        recommendation_id: UUID,
        payload: RecommendationFeedbackRequest,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> RecommendationFeedbackResponse:
        result = RecommendationChoiceService(session).feedback(
            user.user_id, recommendation_id, payload
        )
        session.commit()
        _bump_epoch(user.user_id)
        return result

    return router
