from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from scentiq_api.auth import AuthenticatedUser, CurrentUserDependency
from scentiq_api.repositories import DiscoveryRepository, HybridJobRepository, LayeringRepository
from scentiq_api.schemas import RecommendationBundleResponse
from scentiq_api.services import (
    DiscoveryService,
    HybridJobService,
    LayeringService,
    RecommendationService,
)


def create_recommendations_router(
    get_session: object,
    current_user: CurrentUserDependency,
) -> APIRouter:
    router = APIRouter(prefix="/recommendations", tags=["recommendations"])

    @router.get("", response_model=RecommendationBundleResponse)
    def recommendations(
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> RecommendationBundleResponse:
        response = RecommendationService(
            HybridJobService(HybridJobRepository(session)),
            DiscoveryService(DiscoveryRepository(session)),
            LayeringService(LayeringRepository(session)),
        ).get(user.user_id)
        session.commit()
        return response

    return router
