import json
import logging
from time import perf_counter

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("scentiq_api.request")
diagnostic_logger = logging.getLogger("scentiq_api.diagnostic")
_RUNTIME_HANDLER_NAME = "scentiq-runtime-request"
_DIAGNOSTIC_HANDLER_NAME = "scentiq-runtime-diagnostic"


def format_runtime_event(event: str, level: str, **fields: object) -> str:
    payload: dict[str, object] = {"event": event, "level": level, **fields}
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _configure_logger(target: logging.Logger, handler_name: str) -> None:
    target.disabled = False
    target.setLevel(logging.INFO)

    if any(handler.get_name() == handler_name for handler in target.handlers):
        return

    handler = logging.StreamHandler()
    handler.set_name(handler_name)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(message)s"))
    target.addHandler(handler)


def configure_runtime_logging() -> None:
    logging.getLogger("uvicorn.access").disabled = True
    _configure_logger(logger, _RUNTIME_HANDLER_NAME)
    _configure_logger(diagnostic_logger, _DIAGNOSTIC_HANDLER_NAME)


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started_at = perf_counter()
        status_code = 500

        async def capture_status(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, capture_status)
        finally:
            duration_ms = (perf_counter() - started_at) * 1000
            logger.info(
                format_runtime_event(
                    "http_request_completed",
                    "INFO",
                    method=scope["method"],
                    path=scope["path"],
                    status=status_code,
                    duration_ms=duration_ms,
                ),
                extra={
                    "http_method": scope["method"],
                    "http_path": scope["path"],
                    "http_status": status_code,
                    "duration_ms": duration_ms,
                },
            )
