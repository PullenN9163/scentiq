"""Read-only, validated tools. Identity is bound by the server, never the model."""

import asyncio
import json
from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from scentiq_api.repositories import (
    CollectionRepository,
    DiscoveryRepository,
    FragranceRepository,
    InsightsRepository,
    LayeringRepository,
    WearLogRepository,
)
from scentiq_api.schemas.layering import LayeringGoal
from scentiq_api.services.collection import CollectionService
from scentiq_api.services.discovery import DiscoveryService
from scentiq_api.services.fragrances import FragranceService
from scentiq_api.services.insights import InsightsService
from scentiq_api.services.layering import LayeringService
from scentiq_api.services.wear import WearLogService


class ToolRejected(ValueError):
    pass


class EmptyArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CollectionArgs(EmptyArgs):
    status: Literal["owned", "wishlist"] | None = None
    brand: str | None = Field(default=None, max_length=100)
    query: str | None = Field(default=None, max_length=120)
    fragrance_id: UUID | None = None
    limit: int = Field(default=20, ge=1, le=30)


class RecentArgs(EmptyArgs):
    limit: int = Field(default=10, ge=1, le=30)


class DetailArgs(EmptyArgs):
    fragrance_id: UUID


class DiscoverArgs(EmptyArgs):
    mode: Literal["balance", "taste", "explore", "seasonal"] = "balance"
    season: Literal["spring", "summer", "fall", "winter"] | None = None
    limit: int = Field(default=5, ge=1, le=10)


class LayerArgs(EmptyArgs):
    anchor_fragrance_id: UUID | None = None
    stack_size: Literal[2, 3] = 2
    goal: LayeringGoal | None = None
    season: Literal["spring", "summer", "fall", "winter"] | None = None
    context: (
        Literal["work", "casual", "formal", "date", "dinner", "party", "travel", "gym"] | None
    ) = None
    mode: Literal["safe", "balanced", "contrast", "experimental"] = "balanced"


class EvaluateArgs(EmptyArgs):
    fragrance_ids: list[UUID] = Field(min_length=2, max_length=3)
    goal: LayeringGoal | None = None
    mode: Literal["safe", "balanced", "contrast", "experimental"] = "balanced"


class PreviewArgs(EmptyArgs):
    recommended_for: datetime | None = None
    occasion: (
        Literal["work", "casual", "formal", "date", "dinner", "party", "travel", "gym"] | None
    ) = None
    setting: Literal["indoor", "outdoor", "mixed"] | None = None
    formality: Literal["casual", "smart", "formal"] | None = None
    daypart: Literal["day", "night"] | None = None
    high_celsius: float | None = Field(default=None, ge=-60, le=60)
    low_celsius: float | None = Field(default=None, ge=-60, le=60)


TOOL_ARGS: dict[str, type[BaseModel]] = {
    "get_today_recommendations": EmptyArgs,
    "get_week_plan": EmptyArgs,
    "get_collection": CollectionArgs,
    "get_collection_insights": EmptyArgs,
    "get_recent_wears": RecentArgs,
    "get_neglected_fragrances": RecentArgs,
    "get_discover_recommendations": DiscoverArgs,
    "get_layering_suggestions": LayerArgs,
    "evaluate_layering_stack": EvaluateArgs,
    "get_fragrance_detail": DetailArgs,
    "preview_recommendation": PreviewArgs,
}

TOOL_KINDS = {
    "get_today_recommendations": "recommendation",
    "get_week_plan": "week",
    "get_collection": "collection",
    "get_collection_insights": "insights",
    "get_recent_wears": "wears",
    "get_neglected_fragrances": "insights",
    "get_discover_recommendations": "discover",
    "get_layering_suggestions": "layering",
    "evaluate_layering_stack": "layering",
    "get_fragrance_detail": "fragrance",
    "preview_recommendation": "recommendation",
}

TOOL_LABELS = {
    "get_today_recommendations": "Checking today's weather and plans…",
    "get_week_plan": "Planning your week…",
    "get_collection": "Checking your collection…",
    "get_collection_insights": "Comparing your collection…",
    "get_recent_wears": "Checking recent wears…",
    "get_neglected_fragrances": "Comparing your rotation…",
    "get_discover_recommendations": "Looking for collection gaps…",
    "get_layering_suggestions": "Comparing owned layering options…",
    "evaluate_layering_stack": "Evaluating your stack…",
    "get_fragrance_detail": "Checking source-backed fragrance details…",
    "preview_recommendation": "Matching your occasion…",
}


def definitions() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": name,
            "description": TOOL_LABELS[name],
            "parameters": cls.model_json_schema(),
            "strict": False,
        }
        for name, cls in TOOL_ARGS.items()
    ]


PRIVATE_FIELDS = {
    "user_id",
    "owner_user_id",
    "title",
    "event_title",
    "calendar_name",
    "location_label",
    "description",
    "attendees",
    "meeting_url",
    "access_token",
    "refresh_token",
    "email",
    "raw_payload",
    "source_payload",
    "custom_name",
    "name_override",
    "image_blob_path",
}

MAX_TOOL_OUTPUT_CHARS = 24000


def compact_wear_result(name: str, value: BaseModel) -> dict[str, Any]:
    """Keep actionable wear cards while bounding repeated candidate metadata.

    The full plan and alternatives remain available on Today/My Week. A week's
    daily contexts take priority over event extras so summarization keeps all
    seven dates rather than accidentally dropping the last days of the week.
    """
    result = value.model_dump(mode="json")
    is_plan = "recommendations" in result
    original = result["recommendations"] if is_plan else [result]
    limit = 7 if name == "get_week_plan" else 3
    if name == "get_week_plan" and len(original) > limit:
        daily = [row for row in original if row["context"]["source"] == "day"]
        extras = [row for row in original if row["context"]["source"] != "day"]
        recommendations = (daily + extras)[:limit]
    else:
        recommendations = original[:limit]
    alternative_limit = 1 if name == "get_week_plan" else 2
    trimmed_alternatives = False
    for recommendation in recommendations:
        alternatives = recommendation["alternatives"]
        selected_id = (recommendation.get("decision") or {}).get("selected_fragrance_id")
        chosen = [item for item in alternatives if item["fragrance"]["id"] == selected_id]
        remaining = [item for item in alternatives if item["fragrance"]["id"] != selected_id]
        recommendation["alternatives"] = (chosen + remaining)[:alternative_limit]
        trimmed_alternatives |= len(alternatives) > alternative_limit
        for candidate in [recommendation, *recommendation["alternatives"]]:
            candidate["reasons"] = candidate["reasons"][:3]
            candidate["warnings"] = candidate["warnings"][:3]
            candidate["fragrance"]["top_accords"] = candidate["fragrance"]["top_accords"][:3]
    if is_plan:
        result["recommendations"] = recommendations
        if len(original) > len(recommendations):
            result["gaps"].append("Additional event contexts are available on Today or My Week.")
        if trimmed_alternatives:
            result["gaps"].append(
                "The Agent shows a shortlist of alternatives; "
                "open Today or My Week for all options."
            )
    # If unusually rich metadata still approaches the boundary, remove optional
    # alternatives before rejecting a useful plan. A saved selected candidate is
    # retained so the card reflects the member's persisted decision.
    for recommendation in reversed(recommendations):
        if len(json.dumps(result, ensure_ascii=False)) <= MAX_TOOL_OUTPUT_CHARS:
            break
        selected_id = (recommendation.get("decision") or {}).get("selected_fragrance_id")
        recommendation["alternatives"] = [
            item
            for item in recommendation["alternatives"]
            if item["fragrance"]["id"] == selected_id
        ]
    return result


def minimized(value: Any) -> Any:
    """Bound provider data and omit private fields recursively."""
    if isinstance(value, BaseModel):
        return minimized(value.model_dump(mode="json"))
    if isinstance(value, dict):
        result = {
            key: minimized(item)
            for key, item in value.items()
            if key not in PRIVATE_FIELDS and not (key == "notes" and not isinstance(item, list))
        }
        # Keep the nullable fragrance-card field while dropping the private Blob
        # namespace. Browser cards use the server-mediated image_url instead.
        if "image_blob_path" in value:
            result["image_blob_path"] = None
        return result
    if isinstance(value, list):
        return [minimized(item) for item in value[:30]]
    if isinstance(value, str):
        return value[:600]
    return value


class AgentTools:
    def __init__(
        self,
        session: Session,
        user_id: UUID,
        refresh_context: Callable[[Session, UUID], None] | None = None,
    ) -> None:
        self.session = session
        self.user_id = user_id
        self.refresh_context = refresh_context

    def execute(self, name: str, arguments: str) -> Any:
        cls = TOOL_ARGS.get(name)
        if cls is None or len(arguments) > 4000:
            raise ToolRejected("Unsupported tool")
        try:
            args = cls.model_validate_json(arguments)
        except ValidationError:
            raise ToolRejected("Invalid tool arguments") from None
        raw = self._execute(name, args)
        if name in {"get_week_plan", "get_today_recommendations", "preview_recommendation"}:
            raw = compact_wear_result(name, raw)
        result = minimized(raw)
        if len(json.dumps(result, ensure_ascii=False)) > MAX_TOOL_OUTPUT_CHARS:
            raise ToolRejected("Tool output too large")
        return result

    async def execute_async(self, name: str, arguments: str) -> Any:
        # Each worker owns its session, so cancellation cannot leave the request's
        # session in use after FastAPI closes it. No concurrent use of a Session.
        bind = self.session.get_bind()

        def run() -> Any:
            with Session(bind=bind, expire_on_commit=False) as scoped:
                return type(self)(scoped, self.user_id, self.refresh_context).execute(
                    name, arguments
                )

        return await asyncio.to_thread(run)

    def _execute(self, name: str, args: BaseModel) -> Any:
        session, user_id = self.session, self.user_id
        if name in {"get_today_recommendations", "get_week_plan", "preview_recommendation"}:
            from scentiq_api.schemas.wear_recommendations import RecommendationPreviewRequest
            from scentiq_api.services.wear_recommendations import WearRecommendationService

            if self.refresh_context is not None:
                self.refresh_context(session, user_id)
            wear = WearRecommendationService(session)
            result: BaseModel
            if name == "get_today_recommendations":
                result = wear.today(user_id)
            elif name == "get_week_plan":
                result = wear.week(user_id)
            else:
                result = wear.preview(
                    user_id, RecommendationPreviewRequest(**args.model_dump(), source="agent")
                )
            session.commit()
            return result
        if name == "get_collection":
            assert isinstance(args, CollectionArgs)
            items = CollectionService(
                CollectionRepository(session), FragranceRepository(session)
            ).list_for_user(user_id)
            return [
                item
                for item in items
                if (args.status is None or item.status == args.status)
                and (args.fragrance_id is None or item.fragrance.id == args.fragrance_id)
                and (
                    args.brand is None
                    or args.brand.casefold() in item.fragrance.brand.name.casefold()
                )
                and (
                    args.query is None
                    or args.query.casefold()
                    in (item.fragrance.name + " " + item.fragrance.brand.name).casefold()
                )
            ][: args.limit]
        if name == "get_fragrance_detail":
            assert isinstance(args, DetailArgs)
            return FragranceService(FragranceRepository(session)).get(user_id, args.fragrance_id)
        if name in {"get_collection_insights", "get_neglected_fragrances"}:
            insights = InsightsService(InsightsRepository(session)).for_user(user_id)
            if name == "get_neglected_fragrances":
                assert isinstance(args, RecentArgs)
                return insights.model_dump(mode="json").get("neglected", [])[: args.limit]
            return insights
        if name == "get_recent_wears":
            assert isinstance(args, RecentArgs)
            return WearLogService(
                WearLogRepository(session), CollectionRepository(session)
            ).list_for_user(user_id, limit=args.limit)
        if name == "get_discover_recommendations":
            assert isinstance(args, DiscoverArgs)
            return DiscoveryService(DiscoveryRepository(session)).discover(
                user_id, mode=args.mode, season=args.season, limit=args.limit
            )
        layering = LayeringService(LayeringRepository(session))
        if name == "evaluate_layering_stack":
            assert isinstance(args, EvaluateArgs)
            return layering.evaluate_stack(
                user_id, args.fragrance_ids, mode=args.mode, goal=args.goal
            )
        assert isinstance(args, LayerArgs)
        goal = args.goal or args.season
        if goal is None and args.context in {"date", "dinner", "party"}:
            goal = "evening"
        if goal is None and args.context == "work":
            goal = "daytime"
        stacks = layering.stack_suggestions(
            user_id,
            anchor_id=args.anchor_fragrance_id,
            mode=args.mode,
            goal=goal,
            limit=5,
            include_triples=args.stack_size == 3,
            stack_size=args.stack_size,
        )
        return stacks
