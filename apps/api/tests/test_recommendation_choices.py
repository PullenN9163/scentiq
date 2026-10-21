from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from domain_fixtures import make_brand, make_collection_item, make_fragrance, make_user
from sqlalchemy.orm import Session

from scentiq_api.errors import ApiError
from scentiq_api.models import User
from scentiq_api.schemas.wear_recommendations import (
    RecommendationNextRequest,
    WearRecommendationResponse,
)
from scentiq_api.services.recommendation_choices import RecommendationChoiceService
from scentiq_api.services.wear_recommendations import WearRecommendationService


def batch(
    session: Session, count: int = 3
) -> tuple[User, WearRecommendationService, WearRecommendationResponse]:
    user = make_user(session, email="choices@example.test")
    brand = make_brand(session, name="Choices")
    for index in range(count):
        make_collection_item(
            session,
            user=user,
            fragrance=make_fragrance(session, brand=brand, name=f"Scent {index}"),
        )
    engine = WearRecommendationService(
        session, clock=lambda: datetime(2026, 10, 20, 12, tzinfo=UTC)
    )
    result = engine.today(user.id).recommendations[0]
    return user, engine, result


def test_next_is_unseen_idempotent_and_stable_on_reload(session: Session) -> None:
    user, engine, original = batch(session)
    service = RecommendationChoiceService(session)
    request = RecommendationNextRequest(idempotency_key=uuid4())
    following = service.next(user.id, original.id, request)
    assert following.fragrance.id != original.fragrance.id
    assert following.remaining_options == 1
    assert service.next(user.id, original.id, request).fragrance.id == following.fragrance.id
    assert (
        service.current(
            user.id, engine._response(user.id, engine.get(user.id, original.id))
        ).fragrance.id
        == following.fragrance.id
    )
    last = service.next(user.id, original.id, RecommendationNextRequest(idempotency_key=uuid4()))
    assert len({original.fragrance.id, following.fragrance.id, last.fragrance.id}) == 3
    assert last.options_exhausted
    exhausted = service.next(
        user.id, original.id, RecommendationNextRequest(idempotency_key=uuid4())
    )
    assert exhausted.fragrance.id == last.fragrance.id
    assert exhausted.options_exhausted
    reset = service.next(
        user.id, original.id, RecommendationNextRequest(idempotency_key=uuid4(), reset=True)
    )
    assert reset.fragrance.id == original.fragrance.id
    assert reset.remaining_options == 2


def test_single_candidate_exhaustion_and_tenant_isolation(session: Session) -> None:
    user, _, original = batch(session, 1)
    service = RecommendationChoiceService(session)
    result = service.next(user.id, original.id, RecommendationNextRequest(idempotency_key=uuid4()))
    assert result.fragrance.id == original.fragrance.id
    assert result.options_exhausted
    other = make_user(session, email="otherchoices@example.test")
    with pytest.raises(ApiError) as error:
        service.next(other.id, original.id, RecommendationNextRequest(idempotency_key=uuid4()))
    assert error.value.status_code == 404


def test_reasoned_feedback_preserves_neutral_skip_and_does_not_reject(session: Session) -> None:
    from sqlalchemy import select

    from scentiq_api.models import RecommendationDecision
    from scentiq_api.models.recommendation_choices import RecommendationFeedback
    from scentiq_api.schemas.wear_recommendations import RecommendationFeedbackRequest

    user, _, original = batch(session)
    service = RecommendationChoiceService(session)
    for reason in ("not_today", "too_strong", "dislike_scent"):
        service.feedback(
            user.id,
            original.id,
            RecommendationFeedbackRequest(fragrance_id=original.fragrance.id, reason=reason),
        )
    assert list(session.scalars(select(RecommendationFeedback.reason))) == [
        "not_today",
        "too_strong",
        "dislike_scent",
    ]
    assert session.scalar(select(RecommendationDecision)) is None


def test_stale_concurrent_click_does_not_advance_twice(session: Session) -> None:
    user, _, original = batch(session)
    service = RecommendationChoiceService(session)
    request = RecommendationNextRequest(
        idempotency_key=uuid4(), expected_fragrance_id=original.fragrance.id
    )
    next_choice = service.next(user.id, original.id, request)
    stale = service.next(
        user.id,
        original.id,
        RecommendationNextRequest(
            idempotency_key=uuid4(), expected_fragrance_id=original.fragrance.id
        ),
    )
    assert stale.fragrance.id == next_choice.fragrance.id
    assert stale.remaining_options == next_choice.remaining_options


def test_retry_cannot_restore_retired_ownership(session: Session) -> None:
    from sqlalchemy import select

    from scentiq_api.models import UserCollectionItem

    user, _, original = batch(session)
    service = RecommendationChoiceService(session)
    request = RecommendationNextRequest(idempotency_key=uuid4())
    chosen = service.next(user.id, original.id, request)
    item = session.scalar(
        select(UserCollectionItem).where(
            UserCollectionItem.user_id == user.id,
            UserCollectionItem.fragrance_id == chosen.fragrance.id,
        )
    )
    assert item is not None
    item.status = "sold"
    session.flush()
    with pytest.raises(ApiError) as error:
        service.next(user.id, original.id, request)
    assert error.value.status_code == 409


def test_choice_routes_return_typed_results_and_reject_identity_fields(session: Session) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from scentiq_api.api.v1.surface_choices import create_surface_choices_router
    from scentiq_api.api.v1.wear_recommendations import create_wear_recommendations_router
    from scentiq_api.auth import AuthenticatedUser

    user, _, original = batch(session)
    app = FastAPI()

    def get_session() -> Iterator[Session]:
        yield session

    def current_user() -> AuthenticatedUser:
        return AuthenticatedUser(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            lifecycle_state="active",
        )

    app.include_router(
        create_wear_recommendations_router(get_session, current_user), prefix="/api/v1"
    )
    app.include_router(create_surface_choices_router(get_session, current_user), prefix="/api/v1")
    with TestClient(app) as client:
        following = client.post(
            f"/api/v1/recommendations/{original.id}/next",
            json={
                "idempotency_key": str(uuid4()),
                "expected_fragrance_id": str(original.fragrance.id),
            },
        )
        assert following.status_code == 200, following.text
        assert following.json()["fragrance"]["id"] != str(original.fragrance.id)
        assert following.json()["remaining_options"] == 1
        feedback = client.post(
            f"/api/v1/recommendations/{original.id}/feedback",
            json={"fragrance_id": following.json()["fragrance"]["id"], "reason": "not_today"},
        )
        assert feedback.status_code == 200
        surface = client.post(
            "/api/v1/recommendation-options/layering",
            json={
                "idempotency_key": str(uuid4()),
                "advance": False,
                "parameters": {"mode": "balanced"},
            },
        )
        assert surface.status_code == 200, surface.text
        assert len(surface.json()["selected"]["items"]) >= 2
        forged = client.post(
            "/api/v1/recommendation-options/layering",
            json={"idempotency_key": str(uuid4()), "user_id": str(uuid4())},
        )
        assert forged.status_code == 422


def test_retired_current_selection_requires_refresh_instead_of_repeating_seen(
    session: Session,
) -> None:
    from sqlalchemy import select

    from scentiq_api.models import UserCollectionItem

    user, _, original = batch(session)
    service = RecommendationChoiceService(session)
    chosen = service.next(user.id, original.id, RecommendationNextRequest(idempotency_key=uuid4()))
    item = session.scalar(
        select(UserCollectionItem).where(
            UserCollectionItem.user_id == user.id,
            UserCollectionItem.fragrance_id == chosen.fragrance.id,
        )
    )
    assert item is not None
    item.status = "sold"
    session.flush()
    with pytest.raises(ApiError) as error:
        service.next(user.id, original.id, RecommendationNextRequest(idempotency_key=uuid4()))
    assert error.value.code == "recommendation_changed"


def test_retry_key_cannot_be_reused_with_different_expected_selection(session: Session) -> None:
    user, _, original = batch(session)
    service = RecommendationChoiceService(session)
    key = uuid4()
    result = service.next(
        user.id,
        original.id,
        RecommendationNextRequest(idempotency_key=key, expected_fragrance_id=original.fragrance.id),
    )
    with pytest.raises(ApiError) as error:
        service.next(
            user.id,
            original.id,
            RecommendationNextRequest(
                idempotency_key=key, expected_fragrance_id=result.fragrance.id
            ),
        )
    assert error.value.code == "idempotency_conflict"


def test_accepted_alternative_is_seen_before_requesting_another(session: Session) -> None:
    from scentiq_api.schemas.wear_recommendations import RecommendationDecisionRequest

    user, engine, original = batch(session, 4)
    service = RecommendationChoiceService(session)
    following = service.next(
        user.id, original.id, RecommendationNextRequest(idempotency_key=uuid4())
    )
    replacement = next(
        candidate
        for candidate in following.alternatives
        if candidate.fragrance.id != original.fragrance.id
    )
    engine.decide(
        user.id,
        original.id,
        RecommendationDecisionRequest(
            action="replaced", selected_fragrance_id=replacement.fragrance.id
        ),
    )
    shown = engine._response(user.id, engine.get(user.id, original.id))
    assert shown.fragrance.id == replacement.fragrance.id
    assert shown.remaining_options == 1
    after = service.next(user.id, original.id, RecommendationNextRequest(idempotency_key=uuid4()))
    assert after.fragrance.id not in {
        original.fragrance.id,
        following.fragrance.id,
        replacement.fragrance.id,
    }
    assert after.options_exhausted


def test_each_explicitly_selected_alternative_stays_seen(session: Session) -> None:
    from scentiq_api.schemas.wear_recommendations import RecommendationDecisionRequest

    user, engine, original = batch(session, 4)
    service = RecommendationChoiceService(session)
    following = service.next(
        user.id, original.id, RecommendationNextRequest(idempotency_key=uuid4())
    )
    replacements = [
        candidate
        for candidate in following.alternatives
        if candidate.fragrance.id != original.fragrance.id
    ]
    for candidate in replacements:
        engine.decide(
            user.id,
            original.id,
            RecommendationDecisionRequest(
                action="replaced", selected_fragrance_id=candidate.fragrance.id
            ),
        )
    last = replacements[-1]
    after = service.next(user.id, original.id, RecommendationNextRequest(idempotency_key=uuid4()))
    assert after.fragrance.id == last.fragrance.id
    assert after.options_exhausted
