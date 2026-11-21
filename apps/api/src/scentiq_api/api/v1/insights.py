"""Insight endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from scentiq_api.auth import AuthenticatedUser, CurrentUserDependency
from scentiq_api.repositories import InsightsRepository
from scentiq_api.schemas import CollectionInsightsResponse
from scentiq_api.services import InsightsService


def create_insights_router(
    get_session: object,
    current_user: CurrentUserDependency,
) -> APIRouter:
    router = APIRouter(prefix="/insights", tags=["insights"])

    @router.get("/collection", response_model=CollectionInsightsResponse)
    def collection_insights(
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
        lite: Annotated[bool, Query()] = False,
    ) -> CollectionInsightsResponse:
        service = InsightsService(InsightsRepository(session))
        # Pages that only draw a summary (the accord strip, an empty-collection check) ask for
        # the totals and accord shares; the full breakdown loads every owned fragrance.
        if lite:
            return service.totals_for_user(user.user_id, with_accords=True)
        return service.for_user(user.user_id)

    return router
