from collections.abc import Callable, Iterator

from fastapi import APIRouter
from sqlalchemy.orm import Session

from scentiq_api.api.v1.collection import create_collection_router
from scentiq_api.api.v1.discover import create_discover_router
from scentiq_api.api.v1.fragrances import create_fragrance_router
from scentiq_api.api.v1.identity_events import create_identity_event_router
from scentiq_api.api.v1.insights import create_insights_router
from scentiq_api.api.v1.layering import create_layering_router
from scentiq_api.api.v1.me import create_me_router
from scentiq_api.api.v1.wear_logs import create_wear_log_router
from scentiq_api.api.v1.weather import create_weather_router
from scentiq_api.auth import (
    SigningKeyResolver,
    create_current_user_dependency,
    require_internal_service_token,
)
from scentiq_api.config import Settings
from scentiq_api.integrations.weather import OpenMeteoClient, WeatherProvider


def create_v1_router(
    get_session: Callable[[], Iterator[Session]],
    settings: Settings,
    signing_key_resolver: SigningKeyResolver | None = None,
    weather_provider: WeatherProvider | None = None,
) -> APIRouter:
    """Assemble the v1 router.

    `signing_key_resolver` and `weather_provider` are test seams: passing one
    replaces the JWKS lookup with a local key, or Open-Meteo with a fake. Left
    as None, production uses the real providers.
    """
    router = APIRouter(prefix="/api/v1")
    resolved_weather_provider = weather_provider or OpenMeteoClient(
        forecast_base_url=settings.weather_api_base_url,
        geocoding_base_url=settings.geocoding_api_base_url,
        api_key=settings.open_meteo_api_key_value,
    )

    current_user = create_current_user_dependency(settings, get_session, signing_key_resolver)
    # Only the deletion-rollback route accepts an account already marked
    # pending; every other route refuses it.
    current_user_allowing_pending = create_current_user_dependency(
        settings,
        get_session,
        signing_key_resolver,
        allow_deletion_pending=True,
    )

    router.include_router(
        create_me_router(
            get_session,
            current_user,
            current_user_allowing_pending=current_user_allowing_pending,
            weather_provider=resolved_weather_provider,
        )
    )
    router.include_router(create_fragrance_router(get_session, current_user))
    router.include_router(create_discover_router(get_session, current_user))
    router.include_router(create_layering_router(get_session, current_user))
    router.include_router(create_collection_router(get_session, current_user))
    router.include_router(create_wear_log_router(get_session, current_user))
    router.include_router(create_insights_router(get_session, current_user))
    router.include_router(
        create_weather_router(get_session, current_user, resolved_weather_provider)
    )
    router.include_router(
        create_identity_event_router(get_session, require_internal_service_token(settings))
    )
    return router
