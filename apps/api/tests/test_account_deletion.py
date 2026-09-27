"""Account deletion: pending marking, idempotent event processing, cascade, reconciliation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from domain_fixtures import (
    make_brand,
    make_collection_item,
    make_fragrance,
    make_user,
    make_wear,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from scentiq_api.auth.provisioning import (
    AccountDeletionPendingError,
    resolve_authenticated_user,
)
from scentiq_api.auth.tokens import VerifiedIdentity
from scentiq_api.models import (
    Brand,
    Fragrance,
    IdentityEvent,
    User,
    UserCollectionItem,
    UserIdentity,
    WearLog,
)
from scentiq_api.repositories import IdentityRepository, UserRepository
from scentiq_api.services import AccountDeletionService, IdentityEventService


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def _populated_user(session: Session, *, email: str, subject: str) -> User:
    """A user with a custom brand, custom fragrance, collection item and wear."""
    user = make_user(session, email=email, subject=subject)
    shared_brand = make_brand(session, name=f"Shared {subject}")
    shared = make_fragrance(session, brand=shared_brand, name=f"Curated {subject}")
    custom_brand = make_brand(session, name=f"Custom {subject}", owner_user_id=user.id)
    custom = make_fragrance(
        session,
        brand=custom_brand,
        name=f"Private {subject}",
        owner_user_id=user.id,
    )
    for fragrance in (shared, custom):
        item = make_collection_item(session, user=user, fragrance=fragrance)
        make_wear(session, user=user, item=item)
    session.commit()
    return user


def test_request_deletion_marks_pending(session: Session) -> None:
    user = make_user(session, email="a@example.com", subject="user_a")
    service = AccountDeletionService(UserRepository(session), IdentityRepository(session))

    result = service.request_deletion(user.id)

    assert result.lifecycle_state == "deletion_pending"
    session.refresh(user)
    assert user.lifecycle_state == "deletion_pending"
    assert user.deletion_requested_at is not None


def test_request_deletion_is_idempotent(session: Session) -> None:
    user = make_user(session, email="a@example.com", subject="user_a")
    service = AccountDeletionService(UserRepository(session), IdentityRepository(session))

    first = service.request_deletion(user.id)
    second = service.request_deletion(user.id)

    # The original request time is preserved rather than moved forward.
    assert first.deletion_requested_at == second.deletion_requested_at


def test_pending_account_cannot_authenticate(session: Session) -> None:
    user = make_user(session, email="a@example.com", subject="user_a")
    AccountDeletionService(UserRepository(session), IdentityRepository(session)).request_deletion(
        user.id
    )
    session.commit()

    identity = VerifiedIdentity(subject="user_a", email="a@example.com", display_name=None)

    with pytest.raises(AccountDeletionPendingError):
        resolve_authenticated_user(session, identity)


def test_pending_account_may_still_reach_the_rollback(session: Session) -> None:
    user = make_user(session, email="a@example.com", subject="user_a")
    AccountDeletionService(UserRepository(session), IdentityRepository(session)).request_deletion(
        user.id
    )
    session.commit()

    identity = VerifiedIdentity(subject="user_a", email="a@example.com", display_name=None)

    resolved = resolve_authenticated_user(session, identity, allow_deletion_pending=True)
    assert resolved.user_id == user.id


def test_cancel_deletion_restores_active_state(session: Session) -> None:
    user = make_user(session, email="a@example.com", subject="user_a")
    service = AccountDeletionService(UserRepository(session), IdentityRepository(session))
    service.request_deletion(user.id)

    service.cancel_deletion(user.id)

    session.refresh(user)
    assert user.lifecycle_state == "active"
    assert user.deletion_requested_at is None


def test_user_deleted_event_removes_all_owned_data(session: Session) -> None:
    _populated_user(session, email="a@example.com", subject="user_a")
    service = IdentityEventService(IdentityRepository(session))

    applied = service.handle_user_deleted(event_id="evt_1", subject="user_a")
    session.commit()

    assert applied is True
    assert _count(session, User) == 0
    assert _count(session, UserIdentity) == 0
    assert _count(session, UserCollectionItem) == 0
    assert _count(session, WearLog) == 0
    # The user's own catalog rows are gone...
    assert (
        session.scalar(
            select(func.count()).select_from(Fragrance).where(Fragrance.owner_user_id.is_not(None))
        )
        == 0
    )
    # ...while the shared curated rows survive.
    assert (
        session.scalar(
            select(func.count()).select_from(Fragrance).where(Fragrance.owner_user_id.is_(None))
        )
        == 1
    )
    assert (
        session.scalar(select(func.count()).select_from(Brand).where(Brand.owner_user_id.is_(None)))
        == 1
    )


def test_replayed_event_is_a_no_op(session: Session) -> None:
    _populated_user(session, email="a@example.com", subject="user_a")
    service = IdentityEventService(IdentityRepository(session))

    first = service.handle_user_deleted(event_id="evt_1", subject="user_a")
    session.commit()
    second = service.handle_user_deleted(event_id="evt_1", subject="user_a")
    session.commit()

    assert first is True
    assert second is False
    assert _count(session, IdentityEvent) == 1


def test_event_for_unknown_subject_is_recorded_and_succeeds(session: Session) -> None:
    service = IdentityEventService(IdentityRepository(session))

    applied = service.handle_user_deleted(event_id="evt_x", subject="user_never_existed")
    session.commit()

    # Nothing to purge, but the event is recorded so the provider stops retrying.
    assert applied is False
    assert _count(session, IdentityEvent) == 1


def test_deleting_one_user_leaves_another_untouched(session: Session) -> None:
    _populated_user(session, email="a@example.com", subject="user_a")
    keeper = _populated_user(session, email="b@example.com", subject="user_b")
    service = IdentityEventService(IdentityRepository(session))

    service.handle_user_deleted(event_id="evt_1", subject="user_a")
    session.commit()

    assert _count(session, User) == 1
    remaining = session.get(User, keeper.id)
    assert remaining is not None
    assert (
        session.scalar(
            select(func.count())
            .select_from(UserCollectionItem)
            .where(UserCollectionItem.user_id == keeper.id)
        )
        == 2
    )


def test_reconciliation_purges_stale_pending_users(session: Session) -> None:
    stale = _populated_user(session, email="stale@example.com", subject="user_stale")
    fresh = _populated_user(session, email="fresh@example.com", subject="user_fresh")

    users = UserRepository(session)
    identities = IdentityRepository(session)

    stale_user = users.get(stale.id)
    fresh_user = users.get(fresh.id)
    assert stale_user is not None and fresh_user is not None

    users.mark_deletion_pending(stale_user)
    stale_user.deletion_requested_at = datetime.now(UTC) - timedelta(days=3)
    users.mark_deletion_pending(fresh_user)
    session.commit()

    purged = IdentityEventService(identities).reconcile(now=datetime.now(UTC))
    session.commit()

    # Only the one past the grace window is cleaned up.
    assert purged == [stale.id]
    assert session.get(User, stale.id) is None
    assert session.get(User, fresh.id) is not None


def test_reconciliation_is_safe_to_run_twice(session: Session) -> None:
    user = _populated_user(session, email="a@example.com", subject="user_a")
    users = UserRepository(session)
    target = users.get(user.id)
    assert target is not None
    users.mark_deletion_pending(target)
    target.deletion_requested_at = datetime.now(UTC) - timedelta(days=3)
    session.commit()

    service = IdentityEventService(IdentityRepository(session))
    first = service.reconcile(now=datetime.now(UTC))
    session.commit()
    second = service.reconcile(now=datetime.now(UTC))
    session.commit()

    assert first == [user.id]
    assert second == []
