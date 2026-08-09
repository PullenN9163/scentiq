from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from scentiq_api.api import create_v1_router
from scentiq_api.config import Settings
from scentiq_api.database import (
    DatabaseProbe,
    create_database_engine,
    create_database_probe,
    create_session_factory,
    dispose_database_probe,
)
from scentiq_api.health import create_health_router
from scentiq_api.logging import (
    RequestLoggingMiddleware,
    configure_runtime_logging,
    diagnostic_logger,
    format_runtime_event,
)


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
    database_engine = create_database_engine(resolved_settings.database_url_value)
    session_factory = create_session_factory(database_engine)

    def get_session() -> Iterator[Session]:
        with session_factory() as session:
            try:
                yield session
            except Exception:
                session.rollback()
                raise

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        configure_runtime_logging()
        try:
            yield
        finally:
            database_engine.dispose()
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

    @application.exception_handler(SQLAlchemyError)
    async def handle_database_error(request: Request, _: SQLAlchemyError) -> JSONResponse:
        diagnostic_logger.error(
            format_runtime_event(
                "database_request_failed",
                "ERROR",
                method=request.method,
                path=request.url.path,
            )
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    application.include_router(create_health_router(resolved_database_probe))
    application.include_router(create_v1_router(get_session, resolved_settings.demo_user_id))
    return application


app = create_app()
