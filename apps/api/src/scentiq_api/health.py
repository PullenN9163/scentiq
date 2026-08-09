import logging

from fastapi import APIRouter, Response, status
from sqlalchemy.exc import SQLAlchemyError

from scentiq_api.database import DatabaseProbe

logger = logging.getLogger(__name__)


def create_health_router(database_probe: DatabaseProbe) -> APIRouter:
    router = APIRouter(prefix="/health", tags=["health"])

    @router.get("/live")
    def liveness() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/ready")
    def readiness(response: Response) -> dict[str, str]:
        try:
            database_probe()
        except (SQLAlchemyError, RuntimeError):
            logger.exception("database readiness probe failed", exc_info=False)
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "not_ready"}
        return {"status": "ready"}

    return router
