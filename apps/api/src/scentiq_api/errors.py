"""The single error envelope every ScentIQ API failure is serialised through."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

REQUEST_ID_HEADER = "x-request-id"


class FieldError(BaseModel):
    field: str
    code: str
    message: str


class ErrorResponse(BaseModel):
    code: str
    message: str
    field_errors: list[FieldError] | None = None
    request_id: str | None = None


class ApiError(Exception):
    """An error with a stable machine-readable code and HTTP status."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        field_errors: list[FieldError] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.field_errors = field_errors


def not_found(message: str = "Resource not found") -> ApiError:
    return ApiError(status_code=404, code="not_found", message=message)


def unauthorized(message: str = "Authentication required") -> ApiError:
    return ApiError(status_code=401, code="unauthorized", message=message)


def forbidden(message: str = "Not permitted") -> ApiError:
    return ApiError(status_code=403, code="forbidden", message=message)


def conflict(code: str, message: str) -> ApiError:
    return ApiError(status_code=409, code=code, message=message)


def unprocessable(
    code: str, message: str, field_errors: list[FieldError] | None = None
) -> ApiError:
    return ApiError(status_code=422, code=code, message=message, field_errors=field_errors)


def service_unavailable(code: str, message: str) -> ApiError:
    return ApiError(status_code=503, code=code, message=message)


def request_id_of(request: Request) -> str | None:
    header = request.headers.get(REQUEST_ID_HEADER)
    if header is None:
        return None
    # Bounded and restricted so a caller cannot inject log or header content.
    candidate = header.strip()[:64]
    if not candidate or not all(
        character.isalnum() or character in "-_" for character in candidate
    ):
        return None
    return candidate


def _render(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    field_errors: list[FieldError] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        code=code,
        message=message,
        field_errors=field_errors,
        request_id=request_id_of(request),
    )
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(payload, exclude_none=True),
    )


def _field_errors_from_validation(error: RequestValidationError) -> list[FieldError]:
    field_errors: list[FieldError] = []
    for detail in error.errors():
        location: tuple[Any, ...] = tuple(detail.get("loc", ()))
        # Drop the "body"/"query" prefix so the field path matches the contract.
        trimmed = [str(part) for part in location if part not in {"body", "query", "path"}]
        field_errors.append(
            FieldError(
                field=".".join(trimmed) or "request",
                code=str(detail.get("type", "invalid")),
                # `msg` describes the rule, never the submitted value.
                message=str(detail.get("msg", "Invalid value")),
            )
        )
    return field_errors


_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "unprocessable_entity",
    429: "rate_limited",
    500: "internal_error",
    503: "service_unavailable",
}


async def handle_api_error(request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, ApiError)
    return _render(
        request,
        status_code=error.status_code,
        code=error.code,
        message=error.message,
        field_errors=error.field_errors,
    )


async def handle_validation_error(request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, RequestValidationError)
    return _render(
        request,
        status_code=422,
        code="unprocessable_entity",
        message="The request body failed validation",
        field_errors=_field_errors_from_validation(error),
    )


async def handle_http_exception(request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, StarletteHTTPException)
    code = _STATUS_CODES.get(error.status_code, "error")
    detail = error.detail if isinstance(error.detail, str) else code
    return _render(request, status_code=error.status_code, code=code, message=detail)
