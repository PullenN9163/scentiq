"""Azure OpenAI v1 Responses REST stream; credentials never leave the API."""

import json
from collections.abc import AsyncIterator
from typing import Any, Protocol

import httpx
from azure.identity.aio import DefaultAzureCredential

from scentiq_api.agent.policy import AGENT_INSTRUCTIONS


class AgentProvider(Protocol):
    def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        safety_identifier: str,
        *,
        require_tool: bool,
    ) -> AsyncIterator[dict[str, Any]]: ...


class AzureResponsesProvider:
    def __init__(
        self,
        endpoint: str,
        deployment: str,
        *,
        api_key: str | None = None,
        client_id: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        base = endpoint.rstrip("/")
        self.url = base + ("/responses" if base.endswith("/openai/v1") else "/openai/v1/responses")
        self.deployment = deployment
        self.api_key = api_key
        self.client_id = client_id
        self.client = client

    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        safety_identifier: str,
        *,
        require_tool: bool = False,
    ) -> AsyncIterator[dict[str, Any]]:
        headers: dict[str, str] = {}
        if self.api_key:
            headers["api-key"] = self.api_key
        else:
            async with DefaultAzureCredential(
                managed_identity_client_id=self.client_id
            ) as credential:
                token = await credential.get_token("https://ai.azure.com/.default")
                headers["Authorization"] = "Bearer " + token.token
        payload = {
            "model": self.deployment,
            "instructions": AGENT_INSTRUCTIONS,
            "input": messages,
            "tools": tools,
            "store": False,
            "stream": True,
            "tool_choice": "required" if require_tool else "auto",
            "parallel_tool_calls": False,
            "max_output_tokens": 1200,
            "safety_identifier": safety_identifier,
        }
        if self.client is not None:
            async for event in self._request(self.client, headers, payload):
                yield event
        else:
            async with httpx.AsyncClient(timeout=15.0) as client:
                async for event in self._request(client, headers, payload):
                    yield event

    async def _request(
        self, client: httpx.AsyncClient, headers: dict[str, str], payload: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        async with client.stream("POST", self.url, headers=headers, json=payload) as response:
            response.raise_for_status()
            completed = False
            async for line in response.aiter_lines():
                if not line.startswith("data:") or line[5:].strip() == "[DONE]":
                    continue
                raw = json.loads(line[5:].strip())
                kind = raw.get("type")
                if kind == "response.output_text.delta":
                    yield {"type": "text_delta", "delta": str(raw.get("delta", ""))}
                elif kind == "response.output_item.done":
                    item = raw.get("item", {})
                    if item.get("type") == "function_call":
                        yield {
                            "type": "function_call",
                            "name": item["name"],
                            "arguments": item["arguments"],
                            "call_id": item["call_id"],
                        }
                elif kind == "response.completed":
                    completed = True
                    usage = raw.get("response", {}).get("usage", {})
                    yield {
                        "type": "usage",
                        "input_tokens": usage.get("input_tokens"),
                        "output_tokens": usage.get("output_tokens"),
                    }
                elif kind in {"error", "response.failed", "response.incomplete"}:
                    raise RuntimeError("Agent provider could not complete")
            if not completed:
                raise RuntimeError("Agent provider stream ended early")


class BudgetedProvider:
    """Reserve every advisor iteration from the same global ranking ledger."""

    def __init__(self, provider: AgentProvider, bind: Any, settings: Any) -> None:
        self.provider = provider
        self.deployment = getattr(provider, "deployment", None)
        self.bind = bind
        self.settings = settings

    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        safety_identifier: str,
        *,
        require_tool: bool,
    ) -> AsyncIterator[dict[str, Any]]:
        from scentiq_api.services.ai_ranking import request_cost, reserve_budget, settle_budget

        # UTF-8 bytes upper-bound textual token counts, including tool output.
        input_bytes = len(
            json.dumps(
                {"messages": messages, "tools": tools, "instructions": AGENT_INSTRUCTIONS},
                ensure_ascii=False,
            ).encode("utf-8")
        )
        if input_bytes > self.settings.ai_max_input_bytes:
            raise RuntimeError("Advisor input exceeds inference limit")
        reservation = reserve_budget(
            self.bind,
            self.settings,
            request_cost(self.settings, self.settings.ai_max_input_bytes + 4096, 1200),
        )
        if reservation is None:
            raise RuntimeError("Inference budget exhausted")
        settled = False
        async for event in self.provider.stream(
            messages, tools, safety_identifier, require_tool=require_tool
        ):
            if event.get("type") == "usage" and not settled:
                input_tokens, output_tokens = event.get("input_tokens"), event.get("output_tokens")
                if (
                    type(input_tokens) is int
                    and type(output_tokens) is int
                    and input_tokens >= 0
                    and output_tokens >= 0
                ):
                    settle_budget(
                        self.bind,
                        reservation,
                        request_cost(self.settings, input_tokens, output_tokens),
                    )
                    settled = True
            yield event
