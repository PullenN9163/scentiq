"""Token verification tests.

A local RSA key pair stands in for the provider's signing key, so these run
without network access or a database.
"""

from __future__ import annotations

import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from scentiq_api.auth.tokens import (
    TokenVerificationError,
    VerifiedIdentity,
    verify_token,
)

ISSUER = "https://clerk.example.dev"
AUDIENCE = "scentiq-web"
PARTY = "https://app.scentiq.example"


@pytest.fixture(scope="module")
def signing_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def other_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _token(key: rsa.RSAPrivateKey, **overrides: Any) -> str:
    issued_at = int(time.time())
    claims: dict[str, Any] = {
        "sub": "user_2abcDEF",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "azp": PARTY,
        "email": "member@example.com",
        "name": "Test Member",
        "iat": issued_at,
        "exp": issued_at + 300,
    }
    claims.update(overrides)
    for claim, value in list(claims.items()):
        if value is None:
            del claims[claim]
    return jwt.encode(claims, key, algorithm="RS256")


def _verify(
    token: str,
    key: rsa.RSAPrivateKey,
    *,
    audience: str | None = AUDIENCE,
    parties: list[str] | None = None,
) -> VerifiedIdentity:
    return verify_token(
        token,
        resolve_signing_key=lambda _: key.public_key(),
        issuer=ISSUER,
        audience=audience,
        authorized_parties=[PARTY] if parties is None else parties,
    )


def test_valid_token_yields_identity(signing_key: rsa.RSAPrivateKey) -> None:
    identity = _verify(_token(signing_key), signing_key)

    assert identity.subject == "user_2abcDEF"
    assert identity.email == "member@example.com"
    assert identity.display_name == "Test Member"


def test_expired_token_is_rejected(signing_key: rsa.RSAPrivateKey) -> None:
    issued_at = int(time.time()) - 3600
    token = _token(signing_key, iat=issued_at, exp=issued_at + 60)

    with pytest.raises(TokenVerificationError):
        _verify(token, signing_key)


def test_wrong_issuer_is_rejected(signing_key: rsa.RSAPrivateKey) -> None:
    with pytest.raises(TokenVerificationError):
        _verify(_token(signing_key, iss="https://attacker.example"), signing_key)


def test_wrong_audience_is_rejected(signing_key: rsa.RSAPrivateKey) -> None:
    with pytest.raises(TokenVerificationError):
        _verify(_token(signing_key, aud="someone-else"), signing_key)


def test_token_signed_by_unknown_key_is_rejected(
    signing_key: rsa.RSAPrivateKey,
    other_key: rsa.RSAPrivateKey,
) -> None:
    # Signed by a key the resolver does not hand back.
    with pytest.raises(TokenVerificationError):
        _verify(_token(other_key), signing_key)


def test_unresolvable_signing_key_is_rejected() -> None:
    def failing_resolver(_: str) -> Any:
        raise RuntimeError("jwks fetch failed")

    with pytest.raises(TokenVerificationError):
        verify_token(
            "a.b.c",
            resolve_signing_key=failing_resolver,
            issuer=ISSUER,
            audience=AUDIENCE,
            authorized_parties=[],
        )


def test_unexpected_authorized_party_is_rejected(signing_key: rsa.RSAPrivateKey) -> None:
    with pytest.raises(TokenVerificationError):
        _verify(_token(signing_key, azp="https://evil.example"), signing_key)


def test_missing_authorized_party_is_rejected_when_parties_pinned(
    signing_key: rsa.RSAPrivateKey,
) -> None:
    with pytest.raises(TokenVerificationError):
        _verify(_token(signing_key, azp=None), signing_key)


def test_authorized_party_ignored_when_not_pinned(signing_key: rsa.RSAPrivateKey) -> None:
    identity = _verify(_token(signing_key, azp=None), signing_key, parties=[])

    assert identity.subject == "user_2abcDEF"


def test_unsigned_token_is_rejected(signing_key: rsa.RSAPrivateKey) -> None:
    # alg=none must never be accepted, whatever the token claims.
    unsigned = jwt.encode(
        {"sub": "user_x", "iss": ISSUER, "aud": AUDIENCE, "email": "x@example.com"},
        key="",
        algorithm="none",
    )

    with pytest.raises(TokenVerificationError):
        _verify(unsigned, signing_key)


def test_missing_email_claim_is_rejected(signing_key: rsa.RSAPrivateKey) -> None:
    # The ScentIQ JWT template must supply `email`; without it provisioning
    # would have to invent one, so the token is refused instead.
    with pytest.raises(TokenVerificationError):
        _verify(_token(signing_key, email=None), signing_key)


def test_blank_subject_is_rejected(signing_key: rsa.RSAPrivateKey) -> None:
    with pytest.raises(TokenVerificationError):
        _verify(_token(signing_key, sub="   "), signing_key)


def test_empty_token_is_rejected(signing_key: rsa.RSAPrivateKey) -> None:
    with pytest.raises(TokenVerificationError):
        _verify("   ", signing_key)


def test_display_name_falls_back_to_full_name(signing_key: rsa.RSAPrivateKey) -> None:
    identity = _verify(_token(signing_key, name=None, full_name="Fallback Name"), signing_key)

    assert identity.display_name == "Fallback Name"


def test_missing_display_name_is_allowed(signing_key: rsa.RSAPrivateKey) -> None:
    identity = _verify(_token(signing_key, name=None), signing_key)

    assert identity.display_name is None


def test_rotated_key_is_picked_up(
    signing_key: rsa.RSAPrivateKey,
    other_key: rsa.RSAPrivateKey,
) -> None:
    """A resolver that returns the new key accepts tokens signed with it."""
    rotated = _token(other_key)

    with pytest.raises(TokenVerificationError):
        _verify(rotated, signing_key)

    identity = _verify(rotated, other_key)
    assert identity.subject == "user_2abcDEF"
