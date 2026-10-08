"""Verification of Clerk session tokens.

Signature, issuer, audience, authorized party and expiry are all checked. Keys
are resolved through a cached JWKS client so provider key rotation is picked up
without a restart.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import jwt
from jwt import PyJWKClient

_ALGORITHMS = ["RS256"]
# Clerk's own claims plus the email claim the ScentIQ JWT template must add.
_REQUIRED_CLAIMS = ["sub", "exp", "iat", "iss"]


class TokenVerificationError(Exception):
    """Raised when a presented token is not a valid, current session token."""


class AuthenticationNotConfiguredError(Exception):
    """Raised when no identity provider is configured, so auth fails closed."""


@dataclass(frozen=True, slots=True)
class VerifiedIdentity:
    """The trustworthy subset of a verified token."""

    subject: str
    email: str
    display_name: str | None


class SigningKeyResolver(Protocol):
    # Positional-only: the parameter name is not part of the contract, so any
    # single-argument callable (including a test stub) satisfies it.
    def __call__(self, token: str, /) -> Any: ...


class _JWKSSigningKeyResolver:
    """Resolves a token's signing key, caching the JWKS between requests."""

    def __init__(self, jwks_url: str) -> None:
        # PyJWKClient caches keys and refetches when an unknown `kid` appears,
        # which is what makes provider key rotation transparent here.
        self._client = PyJWKClient(jwks_url, cache_keys=True, lifespan=300)

    def __call__(self, token: str) -> Any:
        return self._client.get_signing_key_from_jwt(token).key


def create_signing_key_resolver(jwks_url: str) -> SigningKeyResolver:
    return _JWKSSigningKeyResolver(jwks_url)


def _require_text(claims: dict[str, Any], claim: str) -> str:
    value = claims.get(claim)
    if not isinstance(value, str) or not value.strip():
        raise TokenVerificationError(f"Token claim '{claim}' is missing or not a string")
    return value.strip()


def _optional_text(claims: dict[str, Any], claim: str) -> str | None:
    value = claims.get(claim)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _verify_authorized_party(claims: dict[str, Any], authorized_parties: list[str]) -> None:
    if not authorized_parties:
        return
    party = claims.get("azp")
    if party is None:
        # Clerk omits `azp` for some token types; absence cannot be treated as
        # a match when the deployment has pinned the allowed parties.
        raise TokenVerificationError("Token is missing the authorized party claim")
    if not isinstance(party, str) or party not in authorized_parties:
        raise TokenVerificationError("Token authorized party is not allowed")


def verify_token(
    token: str,
    *,
    resolve_signing_key: SigningKeyResolver,
    issuer: str,
    audience: str | None,
    authorized_parties: list[str],
    leeway_seconds: int = 0,
) -> VerifiedIdentity:
    """Verify a session token and return the identity it asserts.

    Raises TokenVerificationError for anything that is not a currently valid
    token issued by the configured provider.
    """
    if not token.strip():
        raise TokenVerificationError("Token is empty")

    try:
        signing_key = resolve_signing_key(token)
    except TokenVerificationError:
        raise
    except Exception as error:  # provider/transport failures are opaque here
        raise TokenVerificationError("Token signing key could not be resolved") from error

    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            key=signing_key,
            algorithms=_ALGORITHMS,
            issuer=issuer,
            audience=audience,
            leeway=leeway_seconds,
            options={
                "require": _REQUIRED_CLAIMS,
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_iss": True,
                "verify_aud": audience is not None,
            },
        )
    except jwt.PyJWTError as error:
        # The provider's message can carry token material, so it is not echoed.
        raise TokenVerificationError("Token is not valid") from error

    _verify_authorized_party(claims, authorized_parties)

    subject = _require_text(claims, "sub")
    # The ScentIQ Clerk JWT template must include `email`; provisioning has no
    # other trustworthy source for it and never accepts it from the client.
    email = _require_text(claims, "email")
    display_name = _optional_text(claims, "name") or _optional_text(claims, "full_name")

    return VerifiedIdentity(subject=subject, email=email, display_name=display_name)
