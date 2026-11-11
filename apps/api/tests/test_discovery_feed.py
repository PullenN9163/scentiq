from typing import Any
from uuid import uuid4

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
    payload = {
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
