"""Profile, preference and account-lifecycle access."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from scentiq_api.models import Brand, Fragrance, IdentityEvent, User, UserIdentity, UserPreference

_PREFERENCE_FIELDS = (
    "location",
    "preferred_season",
    "preferred_occasion",
    "preferred_projection",
    "preferred_longevity",
    "maximum_sprays",
)


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: UUID) -> User | None:
        return self._session.get(User, user_id)

    def get_preferences(self, user_id: UUID) -> UserPreference | None:
        return self._session.scalar(select(UserPreference).where(UserPreference.user_id == user_id))

    def set_display_name(self, user: User, display_name: str) -> User:
        user.display_name = display_name
        self._session.flush()
        return user

    def replace_preferences(self, user_id: UUID, values: dict[str, Any]) -> UserPreference:
        preferences = self.get_preferences(user_id)
        if preferences is None:
            preferences = UserPreference(user_id=user_id)
            self._session.add(preferences)
        for field in _PREFERENCE_FIELDS:
            setattr(preferences, field, values.get(field))
        self._session.flush()
        return preferences

    def mark_deletion_pending(self, user: User) -> datetime:
        requested_at = datetime.now(UTC)
        user.lifecycle_state = "deletion_pending"
        user.deletion_requested_at = requested_at
        self._session.flush()
        return requested_at

    def clear_deletion_pending(self, user: User) -> None:
        """Undo the pending mark when the provider deletion request failed."""
        user.lifecycle_state = "active"
        user.deletion_requested_at = None
        self._session.flush()


class IdentityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_user_by_subject(self, provider: str, subject: str) -> User | None:
        statement = (
            select(User)
            .join(UserIdentity, UserIdentity.user_id == User.id)
            .where(UserIdentity.provider == provider, UserIdentity.subject == subject)
        )
        return self._session.scalar(statement)

    def find_event(self, provider: str, event_id: str) -> IdentityEvent | None:
        statement = select(IdentityEvent).where(
            IdentityEvent.provider == provider,
            IdentityEvent.event_id == event_id,
        )
        return self._session.scalar(statement)

    def record_event(
        self,
        *,
        provider: str,
        event_id: str,
        event_type: str,
        subject: str,
    ) -> IdentityEvent:
        event = IdentityEvent(
            provider=provider,
            event_id=event_id,
            event_type=event_type,
            subject=subject,
        )
        self._session.add(event)
        self._session.flush()
        return event

    def mark_event_processed(self, event: IdentityEvent) -> None:
        event.processed_at = datetime.now(UTC)
        self._session.flush()

    def purge_user(self, user_id: UUID) -> None:
        """Remove the user and everything they own, leaving shared rows intact.

        The ON DELETE CASCADE chain from `users` clears collection items, wear
        logs and feedback, wishlists, planning rows and the identity mapping.
        Custom catalog rows cascade from `owner_user_id`; they are deleted
        explicitly first so the order is obvious rather than implicit, and so a
        curated row can never be caught by it.
        """
        self._session.execute(delete(Fragrance).where(Fragrance.owner_user_id == user_id))
        self._session.execute(delete(Brand).where(Brand.owner_user_id == user_id))
        self._session.execute(delete(User).where(User.id == user_id))
        self._session.flush()

    def list_stale_deletion_pending(self, older_than: datetime) -> list[User]:
        """Users whose provider deletion webhook never arrived."""
        statement = select(User).where(
            User.lifecycle_state == "deletion_pending",
            User.deletion_requested_at.is_not(None),
            User.deletion_requested_at < older_than,
        )
        return list(self._session.scalars(statement))
