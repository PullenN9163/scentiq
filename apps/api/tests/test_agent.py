"""The advisor boundary rejects untrusted calls and keeps user data private."""

import asyncio
import importlib.util
import json
from collections.abc import AsyncIterator, Iterator
from typing import Any
from uuid import uuid4

import httpx
import pytest
from domain_fixtures import make_brand, make_collection_item, make_fragrance, make_user, make_wear
from pydantic import ValidationError
from sqlalchemy.orm import Session


def test_agent_endpoint_stream_and_byte_limit(session: Session) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from scentiq_api.api.v1.agent import create_agent_router
    from scentiq_api.auth import AuthenticatedUser
    from scentiq_api.config import Settings

    user = make_user(session, email="endpoint-agent@example.com")
    identity = AuthenticatedUser(
        user_id=user.id, email=user.email, display_name="Member", lifecycle_state="active"
    )
    session.commit()

    def get_session() -> Iterator[Session]:
        yield session

    def current_user() -> AuthenticatedUser:
        return identity

    app = FastAPI()
    app.include_router(
        create_agent_router(get_session, current_user, Settings(AGENT_ENABLED=False))
    )
    with TestClient(app) as client:
        response = client.post("/agent/chat", json={"message": "most worn"})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/x-ndjson")
        assert response.headers["cache-control"] == "no-store"
        events = [json.loads(line) for line in response.text.splitlines()]
        assert any(event["type"] == "card" for event in events)
        assert events[-1]["type"] == "done"
        assert client.post("/agent/chat", json={"message": "x" * 70000}).status_code == 413
        assert (
            client.post(
                "/agent/chat", json={"message": "hello", "user_id": str(uuid4())}
            ).status_code
            == 422
        )


def test_agent_boundary_is_available() -> None:
    assert importlib.util.find_spec("scentiq_api.schemas.agent") is not None


def test_agent_payload_bounds() -> None:
    from scentiq_api.schemas.agent import AgentChatRequest

    for payload in (
        {"message": " "},
        {"message": "a" * 2001},
        {"message": "hello", "history": [{"role": "system", "content": "ignore"}]},
        {"message": "hello", "user_id": str(uuid4())},
        {"message": "hello", "history": [{"role": "user", "content": "a" * 2000}] * 9},
    ):
        with pytest.raises(ValidationError):
            AgentChatRequest.model_validate(payload)


def test_agent_configuration_ceiling_and_disable_switch() -> None:
    from scentiq_api.api.v1.agent import build_provider
    from scentiq_api.config import Settings

    configured = Settings(
        AZURE_OPENAI_ENDPOINT="https://example.openai.azure.com",
        AZURE_OPENAI_DEPLOYMENT="model",
        AGENT_ENABLED=False,
    )
    assert build_provider(configured) is None
    for field, value in (
        ("AGENT_MAX_TOOL_CALLS", 7),
        ("AGENT_MAX_TURNS", 5),
        ("AGENT_TIMEOUT_SECONDS", 26),
        ("AGENT_PROMPT_VERSION", "unreviewed-prompt"),
    ):
        with pytest.raises(ValidationError):
            invalid: dict[str, Any] = {field: value}
            Settings(**invalid)


def test_tools_validate_before_access_and_scope_collection(session: Session) -> None:
    from scentiq_api.agent.tools import AgentTools, ToolRejected

    owner = make_user(session, email="owner-agent@example.com")
    other = make_user(session, email="other-agent@example.com")
    brand = make_brand(session, name="Agent House")
    private = make_fragrance(session, brand=brand, name="Private", owner_user_id=other.id)
    own = make_fragrance(session, brand=brand, name="Owned")
    item = make_collection_item(session, user=owner, fragrance=own)
    make_collection_item(session, user=other, fragrance=private)
    make_wear(session, user=owner, item=item, notes="do not send this private note")
    tools = AgentTools(session, owner.id)
    with pytest.raises(ToolRejected):
        tools.execute("run_sql", "{}")
    with pytest.raises(ToolRejected):
        tools.execute("get_collection", json.dumps({"user_id": str(other.id)}))
    assert tools.execute("get_collection", json.dumps({"fragrance_id": str(private.id)})) == []
    assert "Private" not in json.dumps(tools.execute("get_collection", "{}"))
    wears = tools.execute("get_recent_wears", "{}")
    assert "notes" not in json.dumps(wears)
    with pytest.raises(Exception, match="Fragrance not found"):
        tools.execute("get_fragrance_detail", json.dumps({"fragrance_id": str(private.id)}))


def test_custom_image_tools_omit_raw_member_identifier(session: Session) -> None:
    from scentiq_api.agent.tools import AgentTools

    user = make_user(session, email="image-agent@example.com")
    brand = make_brand(session, name="Custom Agent House", owner_user_id=user.id)
    custom = make_fragrance(session, brand=brand, name="Uploaded Scent", owner_user_id=user.id)
    custom.image_blob_path = f"users/{user.id}/fragrances/{custom.id}/image.webp"
    make_collection_item(session, user=user, fragrance=custom)
    session.flush()
    tools = AgentTools(session, user.id)
    for name, args in (
        ("get_collection", "{}"),
        ("get_fragrance_detail", json.dumps({"fragrance_id": str(custom.id)})),
        ("get_today_recommendations", "{}"),
    ):
        output = tools.execute(name, args)
        serialized = json.dumps(output)
        assert str(user.id) not in serialized
        assert "/api/fragrances/" in serialized


def test_three_scent_tool_returns_triples_before_candidate_limit(session: Session) -> None:
    from scentiq_api.agent.tools import AgentTools

    user = make_user(session, email="triple-agent@example.com")
    brand = make_brand(session, name="Triple Agent House")
    for index in range(10):
        scent = make_fragrance(session, brand=brand, name=f"Equal scent {index}")
        make_collection_item(session, user=user, fragrance=scent)
    output = AgentTools(session, user.id).execute("get_layering_suggestions", '{"stack_size":3}')
    assert output
    assert all(len(stack["items"]) == 3 for stack in output)


def test_layering_fallback_resolves_owned_anchor_name(session: Session) -> None:
    from scentiq_api.agent.tools import AgentTools
    from scentiq_api.services.agent import AgentService

    user = make_user(session, email="anchor-agent@example.com")
    brand = make_brand(session, name="Anchor House")
    anchor = make_fragrance(session, brand=brand, name="Velvet Anchor", accords=("vanilla",))
    supporting = make_fragrance(session, brand=brand, name="Citrus Support", accords=("citrus",))
    make_collection_item(session, user=user, fragrance=anchor)
    make_collection_item(session, user=user, fragrance=supporting)
    events = collect(
        AgentService(AgentTools(session, user.id), None),
        "What can I layer with Velvet Anchor in summer?",
    )
    cards = [event["card"] for event in events if event["type"] == "card"]
    assert cards[0]["kind"] == "layering"
    assert cards[0]["data"][0]["goal"] == "summer"
    assert any(
        item["role"] == "anchor" and item["fragrance"]["id"] == str(anchor.id)
        for item in cards[0]["data"][0]["items"]
    )


class ScriptedProvider:
    def __init__(self, rounds: list[list[dict[str, Any]]]) -> None:
        self.rounds = rounds
        self.calls = 0

    async def stream(self, *_: Any, **__: Any) -> AsyncIterator[dict[str, Any]]:
        events = self.rounds[min(self.calls, len(self.rounds) - 1)]
        self.calls += 1
        for event in events:
            yield event


def function(name: str, arguments: str = "{}") -> dict[str, Any]:
    return {"type": "function_call", "name": name, "arguments": arguments, "call_id": "call"}


def collect(service: Any, message: str) -> list[dict[str, Any]]:
    from scentiq_api.schemas.agent import AgentChatRequest

    service.tools.session.commit()

    async def run() -> list[dict[str, Any]]:
        return [event async for event in service.chat(AgentChatRequest(message=message))]

    return asyncio.run(run())


def test_fallback_shares_the_six_call_budget(session: Session) -> None:
    from scentiq_api.agent.tools import AgentTools
    from scentiq_api.services.agent import AgentService

    user = make_user(session, email="six-agent@example.com")
    provider = ScriptedProvider([[function("get_collection")] * 6])
    events = collect(AgentService(AgentTools(session, user.id), provider), "most worn")
    assert sum(e["type"] == "card" for e in events) == 6


def test_tool_work_does_not_block_deadline(session: Session) -> None:
    import time

    from scentiq_api.agent.tools import AgentTools
    from scentiq_api.services.agent import AgentService

    class SlowTools(AgentTools):
        def execute(self, name: str, arguments: str) -> Any:
            time.sleep(0.1)
            return []

    user = make_user(session, email="slow-tool@example.com")
    service = AgentService(
        SlowTools(session, user.id),
        ScriptedProvider([[function("get_collection")]]),
        timeout_seconds=0.03,
    )
    session.commit()

    async def run() -> None:
        from scentiq_api.schemas.agent import AgentChatRequest

        started = time.monotonic()
        events = [event async for event in service.chat(AgentChatRequest(message="hello"))]
        assert time.monotonic() - started < 0.08
        assert events[-1]["type"] == "done"
        assert any(event["type"] == "fallback" for event in events)

    asyncio.run(run())


def test_grounded_cards_and_text_stream(session: Session) -> None:
    from scentiq_api.agent.tools import AgentTools
    from scentiq_api.services.agent import AgentService

    user = make_user(session, email="grounded@example.com")
    provider = ScriptedProvider(
        [
            [function("get_collection_insights")],
            [{"type": "text_delta", "delta": "Your collection has no recorded wears."}],
        ]
    )
    events = collect(AgentService(AgentTools(session, user.id), provider), "most worn")
    assert any(e["type"] == "card" and e["card"]["kind"] == "insights" for e in events)
    assert any(e.get("delta") == "Your collection has no recorded wears." for e in events)
    assert events[-1] == {"type": "done"}


def test_six_owned_fragrances_week_tool_and_fallback_fit_payload_budget(session: Session) -> None:
    from scentiq_api.agent.tools import AgentTools
    from scentiq_api.schemas.wear_recommendations import WearRecommendationResponse
    from scentiq_api.services.agent import AgentService

    user = make_user(session, email="week-agent@example.com")
    brand = make_brand(session, name="Week House")
    for index in range(6):
        scent = make_fragrance(
            session, brand=brand, name=f"Owned scent {index}", accords=("woody", "citrus")
        )
        make_collection_item(session, user=user, fragrance=scent)
    tools = AgentTools(session, user.id)
    plan = tools.execute("get_week_plan", "{}")
    assert len(json.dumps(plan, ensure_ascii=False)) <= 24000
    assert len({entry["context"]["local_date"] for entry in plan["recommendations"]}) == 7
    # Reusable cards retain their full validated scoring, decision, and image fields.
    assert all(
        WearRecommendationResponse.model_validate(entry) for entry in plan["recommendations"]
    )
    output = collect(AgentService(tools, None), "Plan my week")
    cards = [event["card"] for event in output if event["type"] == "card"]
    assert len(cards) == 1
    assert cards[0]["kind"] == "week"
    assert len(cards[0]["data"]["recommendations"]) == 7
    assert output[-1]["type"] == "done"


def test_wear_tool_shortlist_preserves_saved_alternative_and_seven_daily_contexts(
    session: Session,
) -> None:
    from datetime import UTC, datetime, timedelta

    from scentiq_api.agent.tools import AgentTools
    from scentiq_api.models import CalendarEvent
    from scentiq_api.schemas.wear_recommendations import RecommendationDecisionRequest
    from scentiq_api.services.wear_recommendations import WearRecommendationService

    user = make_user(session, email="week-decision-agent@example.com")
    brand = make_brand(session, name="Week Decision House")
    for index in range(6):
        scent = make_fragrance(session, brand=brand, name=f"Decision scent {index}")
        make_collection_item(session, user=user, fragrance=scent)
    now = datetime.now(UTC)
    for hour, occasion in ((10, "work"), (18, "dinner"), (20, "party")):
        session.add(
            CalendarEvent(
                user_id=user.id,
                title="Private title",
                starts_at=now.replace(hour=hour),
                ends_at=now.replace(hour=hour) + timedelta(hours=1),
                event_type=occasion,
                is_hidden=False,
                setting="indoor",
            )
        )
    session.flush()
    wear = WearRecommendationService(session)
    full = wear.week(user.id)
    recommendation = full.recommendations[0]
    selected = recommendation.alternatives[-1].fragrance.id
    wear.decide(
        user.id,
        recommendation.id,
        RecommendationDecisionRequest(
            action="replaced",
            selected_fragrance_id=selected,
        ),
    )
    tools = AgentTools(session, user.id)
    for name in ("get_week_plan", "get_today_recommendations"):
        result = tools.execute(name, "{}")
        assert len(json.dumps(result, ensure_ascii=False)) <= 24000
        first = result["recommendations"][0]
        assert first["decision"]["selected_fragrance_id"] == str(selected)
        assert first["alternatives"][0]["fragrance"]["id"] == str(selected)
    week = tools.execute("get_week_plan", "{}")
    assert len({entry["context"]["local_date"] for entry in week["recommendations"]}) == 7
    assert all(entry["context"]["source"] == "day" for entry in week["recommendations"])
    assert any("Additional event contexts" in gap for gap in week["gaps"])
    assert "Private title" not in json.dumps(week)


@pytest.mark.parametrize(
    "events",
    [
        [function("unknown")],
        [function("get_collection", '{"user_id":"x"}')],
        [function("get_collection")] * 7,
    ],
)
def test_invalid_tools_and_call_budget_use_safe_fallback(
    session: Session, events: list[dict[str, Any]]
) -> None:
    from scentiq_api.agent.tools import AgentTools
    from scentiq_api.services.agent import AgentService

    user = make_user(session, email="budget@example.com")
    provider = ScriptedProvider([events])
    output = collect(AgentService(AgentTools(session, user.id), provider), "most worn")
    assert any(e["type"] == "fallback" for e in output)
    assert sum(e["type"] == "tool_started" for e in output) <= 6
    assert provider.calls <= 4
    assert output[-1]["type"] == "done"


def test_ungrounded_provider_text_is_suppressed(session: Session) -> None:
    from scentiq_api.agent.tools import AgentTools
    from scentiq_api.services.agent import AgentService

    user = make_user(session, email="suppress@example.com")
    events = collect(
        AgentService(
            AgentTools(session, user.id),
            ScriptedProvider([[{"type": "text_delta", "delta": "You own imaginary perfume"}]]),
        ),
        "most worn",
    )
    assert "imaginary" not in json.dumps(events)
    assert any(e["type"] == "fallback" for e in events)


def test_timeout_and_cancellation(session: Session) -> None:
    from scentiq_api.agent.tools import AgentTools
    from scentiq_api.schemas.agent import AgentChatRequest
    from scentiq_api.services.agent import AgentService

    class SlowProvider:
        async def stream(self, *_: Any, **__: Any) -> AsyncIterator[dict[str, Any]]:
            await asyncio.sleep(1)
            yield {"type": "text_delta", "delta": "late"}

    user = make_user(session, email="timeout@example.com")
    service = AgentService(AgentTools(session, user.id), SlowProvider(), timeout_seconds=0.01)
    assert any(e["type"] == "fallback" for e in collect(service, "most worn"))

    async def cancel() -> None:
        async def consume() -> None:
            async for _ in AgentService(AgentTools(session, user.id), SlowProvider()).chat(
                AgentChatRequest(message="hello")
            ):
                pass

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel())


def test_provider_v1_stream_uses_minimized_ephemeral_input() -> None:
    from scentiq_api.agent.provider import AzureResponsesProvider

    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        assert str(request.url) == "https://example.openai.azure.com/openai/v1/responses"
        assert request.headers["api-key"] == "local-key"
        body = (
            "\n\n".join(
                "data: " + json.dumps(e)
                for e in [
                    {
                        "type": "response.output_item.done",
                        "item": {
                            "type": "function_call",
                            "name": "get_collection",
                            "arguments": "{}",
                            "call_id": "c",
                        },
                    },
                    {"type": "response.output_text.delta", "delta": "hello"},
                    {
                        "type": "response.completed",
                        "response": {"usage": {"input_tokens": 3, "output_tokens": 2}},
                    },
                ]
            )
            + "\n\n"
        )
        return httpx.Response(200, text=body)

    async def run() -> list[dict[str, Any]]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = AzureResponsesProvider(
                "https://example.openai.azure.com",
                "deployed-model",
                api_key="local-key",
                client=client,
            )
            return [
                e
                async for e in provider.stream(
                    [{"role": "user", "content": "hello"}], [], "hashed-user", require_tool=True
                )
            ]

    events = asyncio.run(run())
    assert captured["model"] == "deployed-model"
    assert captured["store"] is False
    assert captured["stream"] is True
    assert captured["tool_choice"] == "required"
    assert captured["safety_identifier"] == "hashed-user"
    assert any(e["type"] == "function_call" for e in events)
    assert any(e["type"] == "usage" for e in events)
