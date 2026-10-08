"""Authentication harness for integration tests.

A locally generated RSA key replaces the provider's JWKS via the
`signing_key_resolver` seam on `create_app`, so integration tests exercise the
real verification path without reaching the network.
"""

from __future__ import annotations

import os
import time
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from scentiq_api.config import Settings

ISSUER = "https://clerk.test.invalid"
AUDIENCE = "scentiq-web"
AUTHORIZED_PARTY = "https://app.test.invalid"
SERVICE_TOKEN = "integration-service-token"

_KEY: rsa.RSAPrivateKey | None = None


def signing_key() -> rsa.RSAPrivateKey:
    global _KEY
    if _KEY is None:
        _KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return _KEY


def resolver() -> Any:
    key = signing_key()
    return lambda _token: key.public_key()


def settings() -> Settings:
    return Settings(
        SCENTIQ_ENV="test",
        DATABASE_URL=os.environ["DATABASE_URL"],
        CORS_ORIGINS="http://localhost:5173",
        CLERK_ISSUER=ISSUER,
        CLERK_AUDIENCE=AUDIENCE,
        CLERK_AUTHORIZED_PARTIES=AUTHORIZED_PARTY,
        INTERNAL_SERVICE_TOKEN=SERVICE_TOKEN,
    )


def unconfigured_settings() -> Settings:
    """Settings with no identity provider, to prove auth fails closed."""
    return Settings(
        SCENTIQ_ENV="test",
        DATABASE_URL=os.environ["DATABASE_URL"],
        CORS_ORIGINS="http://localhost:5173",
    )


# Distinguishes "use the default" from "omit this claim"; a plain None default
# with `or` would silently substitute a default and make it impossible to test
# a token that genuinely lacks the claim.
_OMIT: Any = object()


def token(
    subject: str,
    *,
    email: str | None = _OMIT,
    name: str | None = _OMIT,
    **overrides: Any,
) -> str:
    issued_at = int(time.time())
    claims: dict[str, Any] = {
        "sub": subject,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "azp": AUTHORIZED_PARTY,
        "email": f"{subject}@example.invalid" if email is _OMIT else email,
        "name": "Integration Member" if name is _OMIT else name,
        "iat": issued_at,
        "exp": issued_at + 300,
    }
    claims.update(overrides)
    for claim, value in list(claims.items()):
        if value is None:
            del claims[claim]
    return jwt.encode(claims, signing_key(), algorithm="RS256")


def auth_headers(subject: str, **kwargs: Any) -> dict[str, str]:
    return {"Authorization": f"Bearer {token(subject, **kwargs)}"}
