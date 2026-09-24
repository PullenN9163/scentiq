"""FastAPI dependencies that turn a bearer token into an internal user."""

from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from scentiq_api.auth.provisioning import (
    AccountDeletionPendingError,
    AuthenticatedUser,
    resolve_authenticated_user,
)
from scentiq_api.auth.tokens import (
    SigningKeyResolver,
    TokenVerificationError,
    create_signing_key_resolver,
    verify_token,
)
from scentiq_api.config import Settings
from scentiq_api.errors import forbidden, service_unavailable, unauthorized

SessionDependency = Callable[[], Iterator[Session]]
CurrentUserDependency = Callable[..., AuthenticatedUser]


def _bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise unauthorized("Authorization header is missing")
    scheme, _, credentials = authorization.partition(" ")
    if scheme.lower() != "bearer" or not credentials.strip():
        raise unauthorized("Authorization header must use the bearer scheme")
    return credentials.strip()


def create_current_user_dependency(
    settings: Settings,
    get_session: SessionDependency,
    signing_key_resolver: SigningKeyResolver | None = None,
    *,
    allow_deletion_pending: bool = False,
) -> CurrentUserDependency:
    """Build the dependency that authenticates a request.

    The JWKS client is created once per application so its key cache is shared
    across requests. When no provider is configured the dependency fails closed.

    `allow_deletion_pending` exists for the deletion-rollback endpoint only: a
    pending account is otherwise refused, but the rollback has to be reachable
    by exactly the account that was just marked.
    """
    resolver: SigningKeyResolver | None = signing_key_resolver
    if resolver is None and settings.authentication_is_configured:
        jwks_url = settings.resolved_clerk_jwks_url
        assert jwks_url is not None
        resolver = create_signing_key_resolver(jwks_url)

    def current_user(
        session: Annotated[Session, Depends(get_session)],
        authorization: Annotated[str | None, Header()] = None,
    ) -> AuthenticatedUser:
        if resolver is None or settings.clerk_issuer is None:
            raise service_unavailable(
                "authentication_unavailable",
                "Authentication is not configured for this deployment",
            )

        token = _bearer_token(authorization)
        try:
            identity = verify_token(
                token,
                resolve_signing_key=resolver,
                issuer=settings.clerk_issuer,
                audience=settings.clerk_audience,
                authorized_parties=settings.clerk_authorized_party_list,
            )
        except TokenVerificationError as error:
            raise unauthorized("The session token is not valid") from error

        try:
            return resolve_authenticated_user(
                session,
                identity,
                allow_deletion_pending=allow_deletion_pending,
            )
        except AccountDeletionPendingError as error:
            raise forbidden("This account is being deleted") from error

    return current_user
