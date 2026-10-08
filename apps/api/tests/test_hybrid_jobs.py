from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from domain_fixtures import make_brand, make_fragrance, make_user
from sqlalchemy import select
from sqlalchemy.orm import Session

from scentiq_api.models import AsyncJob, RecommendationSnapshot, RecommendationState
from scentiq_api.repositories import (
    CollectionRepository,
    DiscoveryRepository,
    FragranceRepository,
    HybridJobRepository,
    LayeringRepository,
    UserRepository,
)
from scentiq_api.schemas import CollectionItemCreateRequest, PreferencesUpdateRequest
from scentiq_api.services import (
    CollectionService,
    DiscoveryService,
    HybridJobService,
    LayeringService,
    ProfileService,
    RecommendationService,
)


def _service(session: Session) -> HybridJobService:
    return HybridJobService(HybridJobRepository(session))


def _recommendations(
    session: Session,
    *,
    catalog_version: str = "catalog-a",
    algorithm_version: str = "1",
    max_age: timedelta = timedelta(hours=6),
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> RecommendationService:
    return RecommendationService(
        _service(session),
        DiscoveryService(DiscoveryRepository(session)),
        LayeringService(LayeringRepository(session)),
        catalog_version=catalog_version,
        algorithm_version=algorithm_version,
        max_age=max_age,
        clock=clock,
    )


def test_invalidation_creates_state_and_job_in_the_same_transaction(session: Session) -> None:
    user = make_user(session, email="member@example.com")

    job = _service(session).invalidate_recommendations(user.id, reason="collection_changed")

    state = session.get(RecommendationState, user.id)
    persisted_job = session.scalar(select(AsyncJob).where(AsyncJob.id == job.id))
    assert state is not None
    assert state.input_version == 1
    assert persisted_job is job
    assert job.status == "pending"
    assert job.job_type == "recommendation_bundle"
    assert job.idempotency_key == f"recommendation_bundle:{user.id}:1"


def test_ensure_job_coalesces_duplicate_version(session: Session) -> None:
    user = make_user(session, email="member@example.com")
    service = _service(session)
    first = service.ensure_recommendation_job(user.id, input_version=7, reason="retry")

    second = service.ensure_recommendation_job(user.id, input_version=7, reason="retry")

    assert second.id == first.id
    assert len(session.scalars(select(AsyncJob)).all()) == 1


def test_late_result_is_rejected_when_a_newer_input_version_exists(session: Session) -> None:
    user = make_user(session, email="member@example.com")
    service = _service(session)
    old_job = service.invalidate_recommendations(user.id, reason="collection_changed")
    service.invalidate_recommendations(user.id, reason="preferences_changed")

    promoted = service.promote_recommendation_result(
        old_job.id,
        payload={"discovery": [], "layering": {}},
        algorithm_version="1",
        catalog_version="catalog-a",
    )

    assert promoted is None
    stored_job = session.get(AsyncJob, old_job.id)
    assert stored_job is not None
    assert stored_job.status == "superseded"
    assert session.scalars(select(RecommendationSnapshot)).all() == []


def test_snapshot_lookup_is_scoped_to_member(session: Session) -> None:
    owner = make_user(session, email="owner@example.com")
    other = make_user(session, email="other@example.com")
    service = _service(session)
    job = service.invalidate_recommendations(owner.id, reason="collection_changed")
    snapshot = service.promote_recommendation_result(
        job.id,
        payload={"discovery": [{"fragrance_id": str(uuid4())}], "layering": {}},
        algorithm_version="1",
        catalog_version="catalog-a",
    )

    assert snapshot is not None
    assert service.latest_snapshot(owner.id) is snapshot
    assert service.latest_snapshot(other.id) is None


def test_collection_mutation_invalidates_recommendations(session: Session) -> None:
    user = make_user(session, email="member@example.com")
    brand = make_brand(session, name="House")
    fragrance = make_fragrance(session, brand=brand, name="Scent")
    jobs = _service(session)
    collection = CollectionService(
        CollectionRepository(session),
        FragranceRepository(session),
        jobs,
    )

    collection.add(
        user.id,
        CollectionItemCreateRequest(fragrance_id=fragrance.id, ownership_type="bottle"),
    )

    state = session.get(RecommendationState, user.id)
    assert state is not None
    assert state.input_version == 1
    job = session.scalar(select(AsyncJob))
    assert job is not None
    assert job.reason == "collection_changed"


def test_preference_mutation_invalidates_recommendations(session: Session) -> None:
    user = make_user(session, email="member@example.com")
    jobs = _service(session)
    profile = ProfileService(UserRepository(session), hybrid_jobs=jobs)

    profile.replace_preferences(user.id, PreferencesUpdateRequest(preferred_season="fall"))

    state = session.get(RecommendationState, user.id)
    assert state is not None
    assert state.input_version == 1
    job = session.scalar(select(AsyncJob))
    assert job is not None
    assert job.reason == "preferences_changed"


def test_recommendations_return_valid_current_snapshot(session: Session) -> None:
    user = make_user(session, email="member@example.com")
    jobs = _service(session)
    job = jobs.invalidate_recommendations(user.id, reason="collection_changed")
    jobs.promote_recommendation_result(
        job.id,
        payload={
            "discovery": [],
            "layering": {"safe": [], "contrast": [], "experimental": []},
        },
        algorithm_version="1",
        catalog_version="catalog-a",
    )

    response = _recommendations(session).get(user.id)

    assert response.refresh_status == "fresh"
    assert response.is_stale is False
    assert response.input_version == 1
    assert response.generated_at is not None


def test_recommendations_fall_back_and_queue_initial_refresh(session: Session) -> None:
    user = make_user(session, email="member@example.com")

    response = _recommendations(session).get(user.id)

    assert response.refresh_status == "fallback"
    assert response.is_stale is True
    assert response.payload.discovery == []
    job = session.scalar(select(AsyncJob))
    assert job is not None
    assert job.input_version == 0
    assert job.reason == "cache_miss"


def test_terminal_job_is_retried_only_up_to_bound(session: Session) -> None:
    user = make_user(session, email="member@example.com")
    service = _service(session)
    job = service.ensure_recommendation_job(user.id, input_version=0, reason="cache_miss")
    service.mark_poisoned(
        job.id, execution_id=None, error_code="processing_failed", dequeue_count=5
    )

    retried = service.ensure_recommendation_job(user.id, input_version=0, reason="retry")

    assert retried.id == job.id
    assert retried.status == "pending"
    assert retried.attempt_count == 1
    assert job.execution_id is not None
    service.mark_poisoned(
        job.id,
        execution_id=UUID(job.execution_id),
        error_code="processing_failed",
        dequeue_count=5,
    )
    service.ensure_recommendation_job(user.id, input_version=0, reason="retry")
    assert job.execution_id is not None
    service.mark_poisoned(
        job.id,
        execution_id=UUID(job.execution_id),
        error_code="processing_failed",
        dequeue_count=5,
    )
    retained = service.ensure_recommendation_job(user.id, input_version=0, reason="retry")
    assert retained.status == "poisoned"
    assert retained.attempt_count == 3
    assert retained.last_dequeue_count == 5


def test_snapshot_version_and_age_mismatch_trigger_refresh(session: Session) -> None:
    now = datetime(2026, 10, 6, 12, tzinfo=UTC)
    user = make_user(session, email="member@example.com")
    jobs = _service(session)
    job = jobs.invalidate_recommendations(user.id, reason="collection_changed")
    snapshot = jobs.promote_recommendation_result(
        job.id,
        payload={"discovery": [], "layering": {}},
        algorithm_version="old",
        catalog_version="catalog-a",
    )
    assert snapshot is not None
    snapshot.created_at = now - timedelta(hours=7)

    response = _recommendations(session, clock=lambda: now).get(user.id)

    assert response.is_stale is True
    assert response.refresh_status == "pending"
    assert job.status == "pending"


def test_refresh_overwrites_snapshot_for_same_input_version(session: Session) -> None:
    user = make_user(session, email="member@example.com")
    service = _service(session)
    job = service.invalidate_recommendations(user.id, reason="collection_changed")
    first = service.promote_recommendation_result(
        job.id,
        payload={"discovery": [], "layering": {}},
        algorithm_version="old",
        catalog_version="catalog-a",
    )
    assert first is not None
    service.ensure_recommendation_job(
        user.id, input_version=1, reason="stale_snapshot", force_refresh=True
    )
    assert job.execution_id is not None

    second = service.promote_recommendation_result(
        job.id,
        execution_id=UUID(job.execution_id),
        payload={"discovery": [{"score": 1}], "layering": {}},
        algorithm_version="1",
        catalog_version="catalog-b",
    )

    assert second is first
    assert second.payload["discovery"] == [{"score": 1}]
    assert second.algorithm_version == "1"
    assert second.catalog_version == "catalog-b"


def test_invalid_snapshot_forces_succeeded_job_back_to_pending(session: Session) -> None:
    user = make_user(session, email="member@example.com")
    service = _service(session)
    job = service.invalidate_recommendations(user.id, reason="collection_changed")
    service.promote_recommendation_result(
        job.id,
        payload={"not": "a recommendation bundle"},
        algorithm_version="1",
        catalog_version="catalog-a",
    )

    response = _recommendations(session).get(user.id)

    assert response.refresh_status == "fallback"
    assert job.status == "pending"
    assert job.reason == "invalid_snapshot"


def test_delayed_result_from_prior_execution_cannot_overwrite_refresh(session: Session) -> None:
    user = make_user(session, email="member@example.com")
    service = _service(session)
    job = service.invalidate_recommendations(user.id, reason="collection_changed")
    old_execution = uuid4()
    job.execution_id = str(old_execution)
    snapshot = service.promote_recommendation_result(
        job.id,
        execution_id=old_execution,
        payload={"discovery": [], "layering": {}},
        algorithm_version="old",
        catalog_version="catalog-a",
    )
    assert snapshot is not None
    service.ensure_recommendation_job(
        user.id, input_version=1, reason="stale_snapshot", force_refresh=True
    )
    assert job.execution_id is not None
    new_execution = UUID(job.execution_id)

    delayed = service.promote_recommendation_result(
        job.id,
        execution_id=old_execution,
        payload={"discovery": [{"stale": True}], "layering": {}},
        algorithm_version="old",
        catalog_version="catalog-a",
    )

    assert delayed is None
    assert snapshot.payload["discovery"] == []
    poisoned = service.mark_poisoned(
        job.id,
        execution_id=old_execution,
        error_code="processing_failed",
        dequeue_count=5,
    )
    assert poisoned is None
    assert job.status == "pending"
    assert job.execution_id == str(new_execution)
