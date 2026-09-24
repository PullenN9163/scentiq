"""Dedicated service credential guarding the internal identity-event endpoint.

Only the Next.js webhook route may call it, and it authenticates with a shared
secret rather than a user session token.
"""

from collections.abc import Callable
from hmac import compare_digest
from typing import Annotated

from fastapi import Header

from scentiq_api.config import Settings
from scentiq_api.errors import service_unavailable, unauthorized

SERVICE_TOKEN_HEADER = "x-scentiq-service-token"


def require_internal_service_token(settings: Settings) -> Callable[..., None]:
    def verify(
        x_scentiq_service_token: Annotated[str | None, Header()] = None,
    ) -> None:
        expected = settings.internal_service_token_value
        if expected is None:
            raise service_unavailable(
                "service_credential_unavailable",
                "The internal service credential is not configured",
            )
        if x_scentiq_service_token is None:
            raise unauthorized("Service token is missing")
        # Constant time so a wrong token cannot be discovered by timing.
        if not compare_digest(x_scentiq_service_token, expected):
            raise unauthorized("Service token is not valid")

    return verify
