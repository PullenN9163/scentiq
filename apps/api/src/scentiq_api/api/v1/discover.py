from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from scentiq_api.auth import AuthenticatedUser, CurrentUserDependency
from scentiq_api.repositories import DiscoveryRepository
from scentiq_api.schemas import DiscoveryResult
from scentiq_api.services import DiscoveryService


def create_discover_router(get_session: object, current_user: CurrentUserDependency) -> APIRouter:
    router = APIRouter(prefix="/discover", tags=["discover"])

    @router.get("", response_model=list[DiscoveryResult])
    def discover(
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
        limit: Annotated[int, Query(ge=1, le=50)] = 25,
        offset: Annotated[int, Query(ge=0)] = 0,
        gender: Literal["male", "female", "unisex"] | None = None,
        family: Annotated[str | None, Query(max_length=60)] = None,
        season: Literal["spring", "summer", "fall", "winter"] | None = None,
        accord: Annotated[str | None, Query(max_length=100)] = None,
        minimum_value: Annotated[float | None, Query(ge=1, le=5)] = None,
    ) -> list[DiscoveryResult]:
        return DiscoveryService(DiscoveryRepository(session)).discover(
            user.user_id,
            limit=limit,
            offset=offset,
            gender=gender,
            family=family,
            season=season,
            accord=accord,
            minimum_value=minimum_value,
        )

    return router
