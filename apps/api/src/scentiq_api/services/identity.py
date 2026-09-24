"""Profile, preferences and the two-phase account deletion flow."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from scentiq_api.auth.provisioning import CLERK_PROVIDER
from scentiq_api.errors import not_found
from scentiq_api.repositories import IdentityRepository, UserRepository
from scentiq_api.schemas import (
    DeletionResponse,
    MeResponse,
    MeUpdateRequest,
    PreferencesResponse,
    PreferencesUpdateRequest,
)

# How long a deletion-pending user waits before reconciliation cleans it up.
RECONCILIATION_GRACE = timedelta(hours=24)


def _preferences_response(
    preferences: object | None,
) -> PreferencesResponse:
    if preferences is None:
        return PreferencesResponse()
    return PreferencesResponse.model_validate(preferences)


class ProfileService:
    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    def get(self, user_id: UUID) -> MeResponse:
        user = self._repository.get(user_id)
        if user is None:
            raise not_found("User not found")
        return MeResponse(
            id=str(user.id),
            email=user.email,
            display_name=user.display_name,
            lifecycle_state=user.lifecycle_state,
            created_at=user.created_at,
            preferences=_preferences_response(self._repository.get_preferences(user_id)),
        )

    def update(self, user_id: UUID, request: MeUpdateRequest) -> MeResponse:
        user = self._repository.get(user_id)
        if user is None:
            raise not_found("User not found")
        self._repository.set_display_name(user, request.display_name)
        return self.get(user_id)

    def replace_preferences(
        self,
        user_id: UUID,
        request: PreferencesUpdateRequest,
    ) -> PreferencesResponse:
        preferences = self._repository.replace_preferences(
            user_id,
            request.model_dump(),
        )
        return PreferencesResponse.model_validate(preferences)


class AccountDeletionService:
    """Phase one of deletion: mark pending so the account stops being usable.

    The provider identity is deleted by the caller after this returns, and the
    signed provider webhook drives the actual data removal. Keeping those steps
    separate is what makes the flow recoverable.
    """

    def __init__(self, users: UserRepository, identities: IdentityRepository) -> None:
        self._users = users
        self._identities = identities

    def request_deletion(self, user_id: UUID) -> DeletionResponse:
        user = self._users.get(user_id)
        if user is None:
            raise not_found("User not found")

        if user.lifecycle_state == "deletion_pending" and user.deletion_requested_at is not None:
            # Idempotent: asking twice reports the original request time.
            return DeletionResponse(
                lifecycle_state="deletion_pending",
                deletion_requested_at=user.deletion_requested_at,
            )

        requested_at = self._users.mark_deletion_pending(user)
        return DeletionResponse(
            lifecycle_state="deletion_pending",
            deletion_requested_at=requested_at,
        )

    def cancel_deletion(self, user_id: UUID) -> None:
        """Roll the pending mark back when the provider deletion call failed."""
        user = self._users.get(user_id)
        if user is None:
            raise not_found("User not found")
        self._users.clear_deletion_pending(user)


class IdentityEventService:
    """Phase two: process the provider's signed identity events idempotently."""

    def __init__(self, identities: IdentityRepository) -> None:
        self._identities = identities

    def handle_user_deleted(self, *, event_id: str, subject: str) -> bool:
        """Remove the user behind `subject`. Returns True when work was done.

        Replays are recognised by event id and become no-ops, so the provider
        retrying the webhook cannot delete twice or error.
        """
        existing = self._identities.find_event(CLERK_PROVIDER, event_id)
        if existing is not None and existing.processed_at is not None:
            return False

        event = existing or self._identities.record_event(
            provider=CLERK_PROVIDER,
            event_id=event_id,
            event_type="user.deleted",
            subject=subject,
        )

        user = self._identities.find_user_by_subject(CLERK_PROVIDER, subject)
        if user is not None:
            self._identities.purge_user(user.id)

        # Marked processed either way: a subject with no user is already clean,
        # and recording it stops the provider retrying forever.
        self._identities.mark_event_processed(event)
        return user is not None

    def reconcile(self, *, now: datetime, grace: timedelta = RECONCILIATION_GRACE) -> list[UUID]:
        """Purge deletion-pending users whose webhook cleanup never arrived."""
        stale = self._identities.list_stale_deletion_pending(now - grace)
        purged: list[UUID] = []
        for user in stale:
            user_id = user.id
            self._identities.purge_user(user_id)
            purged.append(user_id)
        return purged
