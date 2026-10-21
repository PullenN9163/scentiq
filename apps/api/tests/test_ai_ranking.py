from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from scentiq_api.config import Settings


def test_budget_atomic_cap_and_settlement(session: Session) -> None:
    from scentiq_api.services.ai_ranking import reserve_budget, settle_budget

    settings = Settings(AI_MONTHLY_BUDGET_USD=0.02)
    first = reserve_budget(session.get_bind(), settings, 15000)
    assert first is not None
    assert reserve_budget(session.get_bind(), settings, 6000) is None
    settle_budget(session.get_bind(), first, 5000)
    assert reserve_budget(session.get_bind(), settings, 15000) is not None


def test_ranking_rejects_invented_ids_and_evidence() -> None:
    from scentiq_api.services.ai_ranking import validate_ranking

    candidates = [{"candidate_id": "a", "baseline_score": 90, "evidence": {"season": "summer"}}]
    assert (
        validate_ranking(
            {"ranking": [{"candidate_id": "b", "evidence_keys": ["season"]}]}, candidates
        )
        is None
    )
    assert (
        validate_ranking(
            {"ranking": [{"candidate_id": "a", "evidence_keys": ["invented"]}]}, candidates
        )
        is None
    )
    result = validate_ranking(
        {"ranking": [{"candidate_id": "a", "evidence_keys": ["season"]}]}, candidates
    )
    assert result is not None
    assert result.ordered_ids == ["a"]
    assert result.explanations == {"a": ["season: summer"]}


def test_disabled_ranking_keeps_baseline(session: Session) -> None:
    from scentiq_api.services.ai_ranking import rank_candidates

    result = rank_candidates(
        session,
        uuid4(),
        candidates=[{"candidate_id": "a", "baseline_score": 10, "evidence": {}}],
        context={},
        fingerprint="v1",
        surface="today",
    )
    assert result.ordered_ids == ["a"]
    assert result.generation_mode == "baseline"


def test_settlement_is_idempotent(session: Session) -> None:
    from scentiq_api.services.ai_ranking import reserve_budget, settle_budget

    settings = Settings(AI_MONTHLY_BUDGET_USD=0.02)
    reservation = reserve_budget(session.get_bind(), settings, 15000)
    assert reservation is not None
    settle_budget(session.get_bind(), reservation, 5000)
    settle_budget(session.get_bind(), reservation, 5000)
    assert reserve_budget(session.get_bind(), settings, 16000) is None


def test_advisor_budget_failure_prevents_provider_call(session: Session) -> None:
    import asyncio

    from scentiq_api.agent.provider import BudgetedProvider

    class Provider:
        async def stream(self, *args: Any, **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
            raise AssertionError("Provider must not run after budget exhaustion")
            yield {}

    provider = BudgetedProvider(Provider(), session.get_bind(), Settings(AI_MONTHLY_BUDGET_USD=0))

    async def run() -> list[dict[str, Any]]:
        return [item async for item in provider.stream([], [], "member", require_tool=False)]

    import pytest

    with pytest.raises(RuntimeError, match="budget"):
        asyncio.run(run())


def test_inference_status_reports_ledger_without_private_payloads(session: Session) -> None:
    from scentiq_api.inference_status import inference_status
    from scentiq_api.services.ai_ranking import reserve_budget

    settings = Settings(AI_MONTHLY_BUDGET_USD=0.02)
    reserve_budget(session.get_bind(), settings, 10000)
    status = inference_status(session, settings)
    assert status["charged_usd"] == 0.01
    assert status["remaining_usd"] == 0.01
    assert status["provider_configured"] is False
    assert "endpoint" not in status


def test_ranker_caches_validated_result_and_never_resends_input(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json
    from datetime import UTC, datetime

    from domain_fixtures import make_user

    from scentiq_api.models.ai_usage import AIUsageMonth
    from scentiq_api.services import ai_ranking

    user = make_user(session, email="rank-cache@example.com")
    session.commit()
    monkeypatch.setenv("AI_RANKING_TODAY_ENABLED", "true")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://model.example.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-mini")
    calls: list[dict[str, Any]] = []

    def request(settings: Settings, payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(payload)
        return {
            "status": "completed",
            "usage": {"input_tokens": 100, "output_tokens": 50},
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "ranking": [
                                        {"candidate_id": "b", "evidence_keys": ["season"]},
                                        {"candidate_id": "a", "evidence_keys": ["season"]},
                                    ]
                                }
                            ),
                        }
                    ]
                }
            ],
        }

    monkeypatch.setattr(ai_ranking, "_request_ranking", request)
    kwargs: dict[str, Any] = dict(
        candidates=[
            {"candidate_id": identifier, "baseline_score": score, "evidence": {"season": season}}
            for identifier, score, season in [("a", 90, "winter"), ("b", 80, "summer")]
        ],
        context={"season": "summer"},
        fingerprint="input-v1",
        surface="today",
    )
    first = ai_ranking.rank_candidates(session, user.id, **kwargs)
    second = ai_ranking.rank_candidates(session, user.id, **kwargs)
    assert first.ordered_ids == ["b", "a"]
    assert second == first
    assert len(calls) == 1
    assert calls[0]["store"] is False
    ledger = session.get(AIUsageMonth, datetime.now(UTC).strftime("%Y-%m"))
    assert ledger is not None
    assert ledger.charged_microusd == 2000


def test_ranker_failure_retains_reservation_and_does_not_retry(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import UTC, datetime

    import httpx
    from domain_fixtures import make_user

    from scentiq_api.models.ai_usage import AIUsageMonth
    from scentiq_api.services import ai_ranking

    user = make_user(session, email="rank-failure@example.com")
    session.commit()
    monkeypatch.setenv("AI_RANKING_TODAY_ENABLED", "true")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://model.example.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-mini")
    calls: list[dict[str, Any]] = []

    def request(settings: Settings, payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(payload)
        raise httpx.ReadTimeout("uncertain request")

    monkeypatch.setattr(ai_ranking, "_request_ranking", request)
    kwargs: dict[str, Any] = dict(
        candidates=[{"candidate_id": "a", "baseline_score": 10, "evidence": {}}],
        context={},
        fingerprint="input-v1",
        surface="today",
    )
    assert ai_ranking.rank_candidates(session, user.id, **kwargs).generation_mode == "baseline"
    assert ai_ranking.rank_candidates(session, user.id, **kwargs).generation_mode == "baseline"
    assert len(calls) == 1
    ledger = session.get(AIUsageMonth, datetime.now(UTC).strftime("%Y-%m"))
    assert ledger is not None
    assert ledger.charged_microusd > 100000


def test_shadow_ranking_reports_baseline_without_changing_selection(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from domain_fixtures import make_user

    from scentiq_api.services import ai_ranking

    user = make_user(session, email="rank-shadow@example.com")
    session.commit()
    monkeypatch.setenv("AI_RANKING_TODAY_ENABLED", "true")
    monkeypatch.setenv("AI_RANKING_SHADOW_ENABLED", "true")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://model.example.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-mini")

    def request(settings: Settings, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "completed",
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "ranking": [
                                        {"candidate_id": "b", "evidence_keys": []},
                                        {"candidate_id": "a", "evidence_keys": []},
                                    ]
                                }
                            ),
                        }
                    ]
                }
            ],
        }

    monkeypatch.setattr(ai_ranking, "_request_ranking", request)
    kwargs: dict[str, Any] = dict(
        candidates=[
            {"candidate_id": "a", "baseline_score": 90, "evidence": {}},
            {"candidate_id": "b", "baseline_score": 80, "evidence": {}},
        ],
        context={},
        fingerprint="v1",
        surface="today",
    )
    assert ai_ranking.rank_candidates(session, user.id, **kwargs).ordered_ids == ["a", "b"]
    assert ai_ranking.rank_candidates(session, user.id, **kwargs).generation_mode == "baseline"


def test_malformed_provider_envelope_falls_back(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from domain_fixtures import make_user

    from scentiq_api.services import ai_ranking

    user = make_user(session, email="rank-malformed@example.com")
    session.commit()
    monkeypatch.setenv("AI_RANKING_TODAY_ENABLED", "true")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://model.example.com")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-mini")
    monkeypatch.setattr(ai_ranking, "_request_ranking", lambda *_: {"usage": [], "output": {}})
    result = ai_ranking.rank_candidates(
        session,
        user.id,
        candidates=[{"candidate_id": "a", "baseline_score": 10, "evidence": {}}],
        context={},
        fingerprint="v1",
        surface="today",
    )
    assert result.generation_mode == "baseline"
