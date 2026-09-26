"""Forecast and place-search endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from scentiq_api.auth import AuthenticatedUser, CurrentUserDependency
from scentiq_api.integrations.weather import WeatherProvider
from scentiq_api.repositories import UserRepository, WeatherRepository
from scentiq_api.schemas import PlaceResponse, WeatherForecastResponse
from scentiq_api.services import WeatherService


def create_weather_router(
    get_session: object,
    current_user: CurrentUserDependency,
    provider: WeatherProvider,
) -> APIRouter:
    router = APIRouter(prefix="/weather", tags=["weather"])

    def _service(session: Session) -> WeatherService:
        return WeatherService(UserRepository(session), WeatherRepository(session), provider)

    @router.get("/forecast", response_model=WeatherForecastResponse)
    def get_forecast(
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> WeatherForecastResponse:
        """The next seven days for the member's saved location.

        `409 location_required` means no location is saved; `409
        location_unresolved` means it could not be found. A cached forecast is
        served with `stale: true` while the provider is unreachable, and `503
        weather_unavailable` is returned only when there is nothing cached.
        """
        forecast = _service(session).forecast(user.user_id)
        # Resolving a location or refreshing the cache writes rows.
        session.commit()
        return forecast

    @router.get("/places", response_model=list[PlaceResponse])
    def search_places(
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
        q: Annotated[str, Query(min_length=2, max_length=120)],
    ) -> list[PlaceResponse]:
        return _service(session).search_places(q)

    return router
