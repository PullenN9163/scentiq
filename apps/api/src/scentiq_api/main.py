from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from scentiq_api.config import Settings
from scentiq_api.database import (
    DatabaseProbe,
    create_database_probe,
    dispose_database_probe,
)
from scentiq_api.health import create_health_router
from scentiq_api.logging import RequestLoggingMiddleware


def create_app(
    settings: Settings | None = None,
    database_probe: DatabaseProbe | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings()
    owns_database_probe = database_probe is None
    resolved_database_probe = (
        create_database_probe(resolved_settings.database_url_value)
        if database_probe is None
        else database_probe
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if owns_database_probe:
                dispose_database_probe(resolved_database_probe)

    application = FastAPI(lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(RequestLoggingMiddleware)
    application.include_router(create_health_router(resolved_database_probe))
    return application


app = create_app()
