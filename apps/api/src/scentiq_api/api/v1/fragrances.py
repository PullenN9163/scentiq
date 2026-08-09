from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from scentiq_api.repositories import FragranceRepository
from scentiq_api.schemas import FragranceDetail, FragranceSummary
from scentiq_api.services import FragranceService

SessionDependency = Callable[[], Iterator[Session]]


def create_fragrance_router(get_session: SessionDependency) -> APIRouter:
    router = APIRouter(prefix="/fragrances", tags=["fragrances"])

    @router.get("", response_model=list[FragranceSummary])
    def list_fragrances(
        session: Annotated[Session, Depends(get_session)],
    ) -> list[FragranceSummary]:
        return FragranceService(FragranceRepository(session)).list()

    @router.get("/{fragrance_id}", response_model=FragranceDetail)
    def get_fragrance(
        fragrance_id: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> FragranceDetail:
        fragrance = FragranceService(FragranceRepository(session)).get(fragrance_id)
        if fragrance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Fragrance not found",
            )
        return fragrance

    return router
