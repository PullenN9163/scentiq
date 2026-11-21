from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from scentiq_api.api.v1.discovery_feed import _safe_snapshot_page, _snapshot_rows
from scentiq_api.config import Settings
from scentiq_api.main import create_app


def _row(*, custom: bool = False) -> dict[str, Any]:
    return {
        "fragrance": {
            "id": str(uuid4()),
            "name": "Snapshot scent",
            "concentration": "EDP",
            "release_year": 2024,
            "image_blob_path": None,
            "image_url": None,
            "gender": "unisex",
            "olfactory_family": "Woody",
            "rating_average": 4.2,
            "rating_count": 20,
            "top_accords": [],
            "longevity_score": None,
            "projection_level": None,
            "brand": {
                "id": str(uuid4()),
                "name": "House",
                "slug": "house",
                "country": None,
            },
            "is_custom": custom,
        },
        "taste_match": 0.5,
        "collection_expansion": 0.4,
        "redundancy_risk": 0.1,
        "score": 0.6,
        "mode": "balance",
        "evidence_coverage": 0.75,
        "reasons": ["Recorded profile evidence."],
    }


def test_discovery_feed_fails_closed_when_authentication_is_unconfigured() -> None:
    settings = Settings(
        SCENTIQ_ENV="test",
        DATABASE_URL="postgresql+psycopg://user:password@localhost/scentiq_test",
        CORS_ORIGINS="http://localhost:5173",
    )
    with TestClient(create_app(settings, database_probe=lambda: None)) as client:
        response = client.get("/api/v1/discovery-feed")
    assert response.status_code == 503


def test_snapshot_modes_keep_legacy_payloads_safe_and_page_mode_rows() -> None:
    balance = _row()
    taste = _row()
    payload: dict[str, object] = {
        "discovery": [balance],
        "discovery_modes": {"balance": [balance], "taste": [taste]},
    }
    balance_rows = _snapshot_rows(payload, "balance", None)
    taste_rows = _snapshot_rows(payload, "taste", None)

    assert str(balance_rows[0].fragrance.id) == balance["fragrance"]["id"]
    assert str(taste_rows[0].fragrance.id) == taste["fragrance"]["id"]
    assert _snapshot_rows({"discovery": [balance]}, "balance", None)
    assert _snapshot_rows({"discovery": [balance]}, "taste", None) == []


def test_snapshot_page_rechecks_owned_excluded_and_shared_visibility() -> None:
    rows = [_row(), _row(), _row(custom=True), _row()]
    from scentiq_api.schemas.discovery import DiscoveryResult

    parsed = [DiscoveryResult.model_validate(row) for row in rows]
    ids = [item.fragrance.id for item in parsed]
    page = _safe_snapshot_page(
        parsed,
        owned_ids={ids[0]},
        excluded_ids={ids[1]},
        shared_ids={ids[1], ids[3]},
        offset=0,
        limit=1,
    )

    assert page is not None
    assert page[0].fragrance.id == ids[3]
    assert (
        _safe_snapshot_page(
            parsed,
            owned_ids={ids[0]},
            excluded_ids={ids[1]},
            shared_ids={ids[1], ids[3]},
            offset=1,
            limit=1,
        )
        is None
    )


def _feed_client(session: Any, user: Any) -> Any:
    from collections.abc import Iterator

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session

    from scentiq_api.api.v1.discovery_feed import create_discovery_feed_router
    from scentiq_api.auth import AuthenticatedUser

    def get_session() -> Iterator[Session]:
        yield session

    def current_user() -> AuthenticatedUser:
        return AuthenticatedUser(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            lifecycle_state="active",
        )

    app = FastAPI()
    app.include_router(
        create_discovery_feed_router(
            get_session,
            current_user,
            catalog_version="catalog-test",
            algorithm_version="algorithm-test",
            max_age_seconds=3600,
        )
    )
    return TestClient(app)


def _add_feed_snapshot(
    session: Any, user: Any, fragrance: Any, payload: dict[str, object], *, input_version: int = 0
) -> None:
    from scentiq_api.models import AsyncJob, RecommendationSnapshot

    row = _row()
    row["fragrance"]["id"] = str(fragrance.id)
    payload = {**payload, "discovery": [row], "discovery_modes": {"balance": [row]}}
    job = AsyncJob(
        job_type="recommendation_bundle",
        status="succeeded",
        user_id=user.id,
        input_version=input_version,
        idempotency_key=f"feed-test:{user.id}:{input_version}",
        reason="feed_test",
        schema_version=1,
        attempt_count=0,
    )
    session.add(job)
    session.flush()
    session.add(
        RecommendationSnapshot(
            user_id=user.id,
            source_job_id=job.id,
            input_version=input_version,
            algorithm_version="algorithm-test",
            catalog_version="catalog-test",
            payload=payload,
        )
    )
    session.flush()


def test_fresh_snapshot_fast_path_trusts_valid_profile_metadata(
    session: Any, monkeypatch: Any
) -> None:
    from domain_fixtures import make_brand, make_fragrance, make_user

    from scentiq_api.services.taste_profile import TasteProfileService

    user = make_user(session, email="feed-fast-path@example.test")
    fragrance = make_fragrance(
        session, brand=make_brand(session, name="Feed fast path"), name="One"
    )
    _add_feed_snapshot(
        session,
        user,
        fragrance,
        {"profile_version": "a" * 64, "excluded_ids": []},
    )

    def unexpected_recompute(self: Any, user_id: Any) -> Any:
        raise AssertionError("fresh snapshot should avoid taste-profile recomputation")

    monkeypatch.setattr(TasteProfileService, "for_user", unexpected_recompute)
    with _feed_client(session, user) as client:
        response = client.get("/discovery-feed?limit=1")
    assert response.status_code == 200, response.text
    assert response.json()["refresh_status"] == "fresh"
    assert len(response.json()["items"]) == 1


def test_snapshot_page_discards_when_version_changes_after_profile_recompute(
    session: Any, monkeypatch: Any
) -> None:
    from domain_fixtures import make_brand, make_fragrance, make_user

    from scentiq_api.repositories import HybridJobRepository
    from scentiq_api.services.taste_profile import TasteProfileService

    user = make_user(session, email="feed-race@example.test")
    fragrance = make_fragrance(session, brand=make_brand(session, name="Feed race"), name="One")
    _add_feed_snapshot(
        session,
        user,
        fragrance,
        {},
    )
    version_reads = 0
    original_profile = TasteProfileService.for_user

    def changing_version(self: Any, user_id: Any) -> int:
        nonlocal version_reads
        version_reads += 1
        return 0 if version_reads == 1 else 1

    profile_reads = 0

    def recompute_profile(self: Any, user_id: Any) -> Any:
        nonlocal profile_reads
        profile_reads += 1
        return original_profile(self, user_id)

    monkeypatch.setattr(HybridJobRepository, "current_input_version", changing_version)
    monkeypatch.setattr(TasteProfileService, "for_user", recompute_profile)
    with _feed_client(session, user) as client:
        response = client.get("/discovery-feed?limit=1")
    assert response.status_code == 200, response.text
    assert response.json()["refresh_status"] == "fallback"
    assert version_reads == 2
    assert profile_reads >= 1


@pytest.mark.parametrize("case", ["stale", "legacy", "invalid_metadata"])
def test_snapshot_profile_fallback_recomputes_for_stale_or_untrusted_metadata(
    session: Any, monkeypatch: Any, case: str
) -> None:
    from domain_fixtures import make_brand, make_fragrance, make_user

    from scentiq_api.services.taste_profile import TasteProfileService

    user = make_user(session, email=f"feed-fallback-{case}@example.test")
    fragrance = make_fragrance(
        session, brand=make_brand(session, name=f"Fallback {case}"), name="One"
    )
    profile_version = TasteProfileService(session).for_user(user.id).version
    if case == "legacy":
        metadata: dict[str, object] = {}
    elif case == "invalid_metadata":
        metadata = {"profile_version": profile_version, "excluded_ids": ["not-a-uuid"]}
    else:
        metadata = {"profile_version": profile_version, "excluded_ids": []}
    _add_feed_snapshot(
        session,
        user,
        fragrance,
        metadata,
        input_version=1 if case == "stale" else 0,
    )
    original = TasteProfileService.for_user
    calls = 0

    def recompute(self: Any, user_id: Any) -> Any:
        nonlocal calls
        calls += 1
        return original(self, user_id)

    monkeypatch.setattr(TasteProfileService, "for_user", recompute)
    with _feed_client(session, user) as client:
        response = client.get("/discovery-feed?limit=1")
    assert response.status_code == 200, response.text
    assert calls >= 1


def test_snapshot_feed_mode_results_are_paginated_after_constraints() -> None:
    rows = [_row() for _ in range(3)]
    from scentiq_api.schemas.discovery import DiscoveryResult

    parsed = [DiscoveryResult.model_validate(row) for row in rows]
    shared = {item.fragrance.id for item in parsed}
    result = _safe_snapshot_page(
        parsed,
        owned_ids=set(),
        excluded_ids=set(),
        shared_ids=shared,
        offset=1,
        limit=1,
    )
    assert result is not None and len(result) == 1
    assert result[0].fragrance.id == parsed[1].fragrance.id
