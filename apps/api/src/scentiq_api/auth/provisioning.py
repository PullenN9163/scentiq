"""Just-in-time provisioning of internal users for verified external identities."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from scentiq_api.auth.tokens import VerifiedIdentity
from scentiq_api.models import User, UserIdentity

CLERK_PROVIDER = "clerk"


class AccountDeletionPendingError(Exception):
    """Raised when the identity belongs to a user awaiting deletion cleanup."""


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """An authenticated caller, resolved to an internal user."""

    user_id: UUID
    email: str
    display_name: str
    lifecycle_state: str


def _fallback_display_name(identity: VerifiedIdentity) -> str:
    if identity.display_name is not None:
        return identity.display_name[:120]
    local_part = identity.email.split("@", 1)[0]
    return (local_part or "ScentIQ member")[:120]


def _lookup(session: Session, subject: str) -> User | None:
    statement = (
        select(User)
        .join(UserIdentity, UserIdentity.user_id == User.id)
        .where(UserIdentity.provider == CLERK_PROVIDER, UserIdentity.subject == subject)
    )
    return session.scalar(statement)


def resolve_authenticated_user(
    session: Session,
    identity: VerifiedIdentity,
    *,
    allow_deletion_pending: bool = False,
) -> AuthenticatedUser:
    """Return the internal user for a verified identity, creating it if needed.

    Two concurrent first requests race on the same identity. The unique
    constraint on (provider, subject) decides the winner; the loser rolls back
    and re-reads the row the winner committed.
    """
    existing = _lookup(session, identity.subject)
    if existing is None:
        user = User(
            email=identity.email,
            display_name=_fallback_display_name(identity),
            is_demo=False,
            lifecycle_state="active",
        )
        session.add(user)
        try:
            session.flush()
            session.add(
                UserIdentity(
                    provider=CLERK_PROVIDER,
                    subject=identity.subject,
                    user_id=user.id,
                )
            )
            # Committed here rather than left to the request: the identity
            # mapping must survive even if the rest of the request fails.
            session.commit()
            existing = user
        except IntegrityError:
            # Lost the race (or the email is already attached to another
            # identity). Re-read rather than inventing a second user.
            session.rollback()
            existing = _lookup(session, identity.subject)
            if existing is None:
                raise

    if existing.lifecycle_state == "deletion_pending" and not allow_deletion_pending:
        raise AccountDeletionPendingError

    return AuthenticatedUser(
        user_id=existing.id,
        email=existing.email,
        display_name=existing.display_name,
        lifecycle_state=existing.lifecycle_state,
    )
