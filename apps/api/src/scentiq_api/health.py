from fastapi import APIRouter, Response, status
from sqlalchemy.exc import SQLAlchemyError

from scentiq_api.database import DatabaseProbe
from scentiq_api.logging import diagnostic_logger, format_runtime_event


def create_health_router(database_probe: DatabaseProbe) -> APIRouter:
    router = APIRouter(prefix="/health", tags=["health"])

    @router.get("")
    @router.get("/live")
    def liveness() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/ready")
    def readiness(response: Response) -> dict[str, str]:
        try:
            database_probe()
        except (SQLAlchemyError, RuntimeError) as error:
            diagnostic_logger.warning(
                format_runtime_event(
                    "database_readiness_failed",
                    "WARNING",
                    operation="database_readiness_probe",
                    exception_type=type(error).__name__,
                ),
                extra={
                    "operation": "database_readiness_probe",
                    "exception_type": type(error).__name__,
                },
            )
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "not_ready"}
        return {"status": "ready"}

    return router
