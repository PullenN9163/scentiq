from uuid import uuid4

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


def _recommendations(session: Session) -> RecommendationService:
    return RecommendationService(
        _service(session),
        DiscoveryService(DiscoveryRepository(session)),
        LayeringService(LayeringRepository(session)),
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
    profile = ProfileService(UserRepository(session), jobs)

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
