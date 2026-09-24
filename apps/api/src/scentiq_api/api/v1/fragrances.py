"""Catalog endpoints. Visibility is always the authenticated caller's."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from scentiq_api.auth import AuthenticatedUser, CurrentUserDependency
from scentiq_api.repositories import FragranceRepository
from scentiq_api.repositories.fragrances import MAX_SEARCH_LIMIT
from scentiq_api.schemas import FragranceCreateRequest, FragranceDetail, FragranceSummary
from scentiq_api.services import FragranceService


def create_fragrance_router(
    get_session: object,
    current_user: CurrentUserDependency,
) -> APIRouter:
    router = APIRouter(prefix="/fragrances", tags=["fragrances"])

    @router.get("", response_model=list[FragranceSummary])
    def list_fragrances(
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
        q: Annotated[str | None, Query(max_length=120)] = None,
        limit: Annotated[int, Query(ge=1, le=MAX_SEARCH_LIMIT)] = 25,
    ) -> list[FragranceSummary]:
        return FragranceService(FragranceRepository(session)).search(
            user.user_id,
            query=q,
            limit=limit,
        )

    @router.post("", response_model=FragranceSummary, status_code=status.HTTP_201_CREATED)
    def create_fragrance(
        payload: FragranceCreateRequest,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> FragranceSummary:
        created = FragranceService(FragranceRepository(session)).create_custom(
            user.user_id,
            payload,
        )
        session.commit()
        return created

    @router.get("/{fragrance_id}", response_model=FragranceDetail)
    def get_fragrance(
        fragrance_id: UUID,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> FragranceDetail:
        return FragranceService(FragranceRepository(session)).get(user.user_id, fragrance_id)

    return router
