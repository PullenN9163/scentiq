"""Bounded model/tool loop and deterministic fallbacks for the fragrance advisor."""

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

from scentiq_api.agent.policy import AGENT_PROMPT_VERSION
from scentiq_api.agent.provider import AgentProvider
from scentiq_api.agent.tools import TOOL_KINDS, TOOL_LABELS, AgentTools, ToolRejected, definitions
from scentiq_api.logging import format_runtime_event
from scentiq_api.schemas.agent import AgentChatRequest

logger = logging.getLogger("scentiq_api.diagnostic")
MAX_TOOL_CALLS = 6
MAX_ITERATIONS = 4


class AgentService:
    def __init__(
        self,
        tools: AgentTools,
        provider: AgentProvider | None,
        *,
        timeout_seconds: float = 25.0,
        max_tool_calls: int = MAX_TOOL_CALLS,
        max_iterations: int = MAX_ITERATIONS,
        prompt_version: str = AGENT_PROMPT_VERSION,
    ) -> None:
        self.tools = tools
        self.provider = provider
        self.timeout_seconds = min(timeout_seconds, 25.0)
        self.max_tool_calls = min(max_tool_calls, MAX_TOOL_CALLS)
        self.max_iterations = min(max_iterations, MAX_ITERATIONS)
        self.prompt_version = prompt_version

    async def chat(self, request: AgentChatRequest) -> AsyncIterator[dict[str, Any]]:
        started = time.monotonic()
        used: list[str] = []
        fallback = False
        error_kind: str | None = None
        usage: dict[str, Any] = {}
        yield {"type": "status", "label": "Checking your ScentIQ context…"}
        try:
            # Reserve part of the same overall deadline for the deterministic answer.
            async with asyncio.timeout(self.timeout_seconds * 0.9):
                if self.provider is None:
                    raise RuntimeError("Provider unavailable")
                messages: list[dict[str, Any]] = [turn.model_dump() for turn in request.history]
                messages.append({"role": "user", "content": request.message})
                identifier = hashlib.sha256(str(self.tools.user_id).encode()).hexdigest()
                for _ in range(self.max_iterations):
                    calls: list[dict[str, Any]] = []
                    text_seen = False
                    async for event in self.provider.stream(
                        messages, definitions(), identifier, require_tool=not used
                    ):
                        if event["type"] == "function_call":
                            calls.append(event)
                            if len(used) + len(calls) > self.max_tool_calls:
                                raise ToolRejected("Tool limit reached")
                        elif event["type"] == "usage":
                            usage = {
                                key: event.get(key) for key in ("input_tokens", "output_tokens")
                            }
                        elif event["type"] == "text_delta" and used:
                            text_seen = True
                            yield {"type": "text_delta", "delta": event["delta"]}
                    if not calls:
                        if not used or not text_seen:
                            raise ToolRejected("No grounded answer")
                        break
                    for call in calls:
                        name = call["name"]
                        if name not in TOOL_LABELS:
                            raise ToolRejected("Unsupported tool")
                        yield {"type": "tool_started", "tool": name, "label": TOOL_LABELS[name]}
                        used.append(name)
                        result = await self.tools.execute_async(name, call["arguments"])
                        yield {"type": "tool_finished", "tool": name, "label": "Context ready"}
                        yield {"type": "card", "card": {"kind": TOOL_KINDS[name], "data": result}}
                        messages.append(
                            {key: call[key] for key in ("type", "name", "arguments", "call_id")}
                        )
                        messages.append(
                            {
                                "type": "function_call_output",
                                "call_id": call["call_id"],
                                "output": json.dumps(result),
                            }
                        )
                else:
                    raise ToolRejected("Iteration limit reached")
        except asyncio.CancelledError:
            error_kind = "cancelled"
            raise
        except Exception as exc:
            error_kind = "timeout" if isinstance(exc, TimeoutError) else type(exc).__name__
            fallback = True
            yield {
                "type": "fallback",
                "label": "AI explanation unavailable — showing ScentIQ's structured answer",
            }
            try:
                name, args, explanation = self.fallback_intent(request.message)
                if name and len(used) < self.max_tool_calls:
                    remaining = self.timeout_seconds - (time.monotonic() - started)
                    if remaining <= 0:
                        raise TimeoutError
                    async with asyncio.timeout(remaining):
                        if (
                            name == "get_layering_suggestions"
                            and len(used) + 2 <= self.max_tool_calls
                        ):
                            used.append("get_collection")
                            owned = await self.tools.execute_async(
                                "get_collection", '{"status":"owned","limit":30}'
                            )
                            matches = sorted(
                                [
                                    item
                                    for item in owned
                                    if item["fragrance"]["name"].casefold()
                                    in request.message.casefold()
                                ],
                                key=lambda item: len(item["fragrance"]["name"]),
                                reverse=True,
                            )
                            if matches and (
                                len(matches) == 1
                                or len(matches[0]["fragrance"]["name"])
                                > len(matches[1]["fragrance"]["name"])
                            ):
                                args["anchor_fragrance_id"] = matches[0]["fragrance"]["id"]
                            elif any(
                                word in request.message.casefold() for word in ("with ", "around ")
                            ):
                                yield {
                                    "type": "card",
                                    "card": {"kind": "collection", "data": owned},
                                }
                                yield {
                                    "type": "text_delta",
                                    "delta": (
                                        "Which owned fragrance should anchor the stack? "
                                        "Choose a name from your collection above."
                                    ),
                                }
                                yield {"type": "done"}
                                return
                        used.append(name)
                        result = await self.tools.execute_async(name, json.dumps(args))
                    yield {"type": "card", "card": {"kind": TOOL_KINDS[name], "data": result}}
                    yield {"type": "text_delta", "delta": explanation}
                else:
                    yield {
                        "type": "text_delta",
                        "delta": (
                            "Use the ScentIQ results above, or try a more specific question. "
                            "I can help with wear recommendations, collection, and layering."
                        ),
                    }
            except asyncio.CancelledError:
                error_kind = "cancelled"
                raise
            except Exception:
                yield {
                    "type": "text_delta",
                    "delta": (
                        "Your ScentIQ context is temporarily unavailable. "
                        "Check your collection and location in Settings, then try again."
                    ),
                }
        finally:
            fields = {
                "duration_ms": round((time.monotonic() - started) * 1000),
                "prompt_version": self.prompt_version,
                "model_deployment": getattr(self.provider, "deployment", None),
                "tool_count": len(used),
                "tool_names": used,
                "model_error": error_kind,
                "fallback_used": fallback,
                "token_usage": usage,
            }
            logger.info(format_runtime_event("agent_request", "INFO", **fields), extra=fields)
        yield {"type": "done"}

    @staticmethod
    def fallback_intent(message: str) -> tuple[str | None, dict[str, Any], str]:
        text = message.casefold()
        if any(term in text for term in ("neglect", "rarely", "forgotten")):
            return (
                "get_neglected_fragrances",
                {},
                "These owned fragrances have the least recorded rotation. "
                "Missing wear logs may affect this view.",
            )
        if any(term in text for term in ("most worn", "most wear", "worth", "invest", "spent")):
            return (
                "get_collection_insights",
                {},
                "Here are your recorded collection and wear metrics. "
                "Recorded purchase value is not current resale value.",
            )
        if "week" in text:
            return (
                "get_week_plan",
                {},
                "Here is your deterministic seven-day plan, with any missing context shown.",
            )
        if any(term in text for term in ("layer", "stack", "combo")):
            goal = (
                "summer"
                if "summer" in text
                else "winter"
                if "winter" in text
                else "evening"
                if any(word in text for word in ("tonight", "date", "dinner"))
                else None
            )
            return (
                "get_layering_suggestions",
                {
                    "stack_size": 3
                    if any(word in text for word in ("three", "3-", "3 scent"))
                    else 2,
                    "goal": goal,
                },
                "These owned stacks come from ScentIQ's deterministic layering engine. "
                "Spray plans are starting guidance.",
            )
        if (
            any(term in text for term in ("buy", "missing", "winter", "summer", "discover"))
            and "wear" not in text
        ):
            season = "winter" if "winter" in text else "summer" if "summer" in text else None
            return (
                "get_discover_recommendations",
                {"mode": "seasonal" if season else "balance", "season": season},
                "These catalog suggestions use collection coverage and recorded metadata; "
                "no live prices are available.",
            )
        if "tomorrow" in text:
            return (
                "preview_recommendation",
                {"recommended_for": (datetime.now(UTC) + timedelta(days=1)).isoformat()},
                "Here is a deterministic preview for tomorrow; "
                "check its context gaps before wearing.",
            )
        for word, occasion in (
            ("work", "work"),
            ("office", "work"),
            ("date", "date"),
            ("dinner", "dinner"),
        ):
            if word in text:
                return (
                    "preview_recommendation",
                    {
                        "occasion": occasion,
                        "daypart": "night" if occasion in {"date", "dinner"} else "day",
                    },
                    "Here is a deterministic recommendation for your requested occasion.",
                )
        if any(term in text for term in ("wear", "today")):
            return (
                "get_today_recommendations",
                {},
                "Here are today's deterministic recommendations with reasons, "
                "spray guidance, and context gaps.",
            )
        return None, {}, ""
