"""One authoritative wear engine for Today, Week, manual previews and Agent tools."""

import hashlib
import json
import time as timer
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from statistics import mean
from typing import Any, cast
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from scentiq_api.errors import not_found, unprocessable
from scentiq_api.logging import diagnostic_logger, format_runtime_event
from scentiq_api.models import (
    Fragrance,
    FragranceAccord,
    InteractionEvent,
    Recommendation,
    RecommendationCandidate,
    RecommendationDecision,
    UserCollectionItem,
    UserPreference,
    UserTasteProfile,
    WearFeedback,
    WearLog,
)
from scentiq_api.repositories.calendar import CalendarRepository
from scentiq_api.repositories.weather import WeatherRepository
from scentiq_api.schemas.layering import LayeringGoal, LayeringStackSuggestion
from scentiq_api.schemas.wear import WearLogResponse
from scentiq_api.schemas.wear_recommendations import (
    RecommendationContext,
    RecommendationDecisionRequest,
    RecommendationDecisionResponse,
    RecommendationPreviewRequest,
    RecommendationWearRequest,
    WearRecommendationCandidate,
    WearRecommendationPlan,
    WearRecommendationResponse,
)
from scentiq_api.services.fragrances import to_fragrance_summary
from scentiq_api.services.layer_stack_scoring import signals
from scentiq_api.services.taste_profile import (
    TasteProfileService,
    exploration_bonus,
    polarity,
    taste_affinity,
)
from scentiq_api.services.wear_scoring import (
    COMPONENT_MAXIMUM,
    WEAR_ALGORITHM_VERSION,
    CandidateInput,
    score_candidate,
)

BLEND_WINDOW = 6.0  # a blend must score within this many points of the best single
MAX_BLENDS = 2


def blend_key_for(fragrance_ids: list[UUID]) -> str:
    return hashlib.sha1(
        ",".join(sorted(str(item) for item in fragrance_ids)).encode(), usedforsecurity=False
    ).hexdigest()


def blend_goal(context: RecommendationContext) -> str:
    """Pick the layering goal that best fits the day's weather, daypart and season."""
    if context.high_celsius is not None and context.high_celsius <= 10:
        return "warmer"
    if context.high_celsius is not None and context.high_celsius >= 26:
        return "fresher"
    return "evening" if context.daypart == "night" else "daytime"


def aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def season_for(day: date, latitude: float | None) -> str:
    season = ("winter", "spring", "summer", "fall")[(day.month % 12) // 3]
    if latitude is not None and latitude < 0:
        season = {"winter": "summer", "spring": "fall", "summer": "winter", "fall": "spring"}[
            season
        ]
    return season


class WearRecommendationService:
    def __init__(
        self, session: Session, *, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        self.session = session
        self.clock = clock

    def _preferences(self, user_id: UUID) -> UserPreference | None:
        return self.session.get(UserPreference, user_id)

    def _zone(self, preferences: UserPreference | None) -> ZoneInfo:
        try:
            return ZoneInfo(preferences.timezone if preferences and preferences.timezone else "UTC")
        except ZoneInfoNotFoundError:
            return ZoneInfo("UTC")

    def _owned(self, user_id: UUID) -> list[UserCollectionItem]:
        return list(
            self.session.scalars(
                select(UserCollectionItem)
                .where(UserCollectionItem.user_id == user_id, UserCollectionItem.status == "owned")
                .options(
                    joinedload(UserCollectionItem.fragrance).joinedload(Fragrance.brand),
                    joinedload(UserCollectionItem.fragrance).selectinload(Fragrance.seasons),
                    joinedload(UserCollectionItem.fragrance).selectinload(Fragrance.occasions),
                    joinedload(UserCollectionItem.fragrance).joinedload(Fragrance.community),
                    joinedload(UserCollectionItem.fragrance)
                    .selectinload(Fragrance.accord_links)
                    .joinedload(FragranceAccord.accord),
                )
                .order_by(UserCollectionItem.created_at, UserCollectionItem.id)
            )
        )

    def _context(
        self, user_id: UUID, when: datetime, *, source: str, key: str
    ) -> RecommendationContext:
        preferences = self._preferences(user_id)
        zone = self._zone(preferences)
        local = when.astimezone(zone)
        weather = WeatherRepository(self.session).get_day(user_id, local.date())
        # A changed location must not re-use a snapshot for the old place.
        if weather and (not preferences or weather.location_label != preferences.location_label):
            weather = None
        return RecommendationContext.model_validate(
            {
                "context_key": key,
                "recommended_for": when,
                "local_date": local.date(),
                "timezone": str(zone),
                "daypart": "night" if local.hour >= 18 or local.hour < 6 else "day",
                "season": season_for(
                    local.date(),
                    float(preferences.latitude)
                    if preferences and preferences.latitude is not None
                    else None,
                ),
                "source": source,
                "high_celsius": float(weather.temperature_celsius) if weather else None,
                "low_celsius": float(weather.temperature_min_celsius)
                if weather and weather.temperature_min_celsius is not None
                else None,
                "humidity": weather.humidity if weather else None,
                "precipitation_probability": float(weather.precipitation_probability)
                if weather and weather.precipitation_probability is not None
                else None,
                "condition": weather.condition if weather else None,
            }
        )

    def _plan(self, user_id: UUID, days: int) -> WearRecommendationPlan:
        preferences = self._preferences(user_id)
        zone = self._zone(preferences)
        today = self.clock().astimezone(zone).date()
        owned = self._owned(user_id)
        gaps = []
        if not owned:
            gaps.append("Add an owned fragrance to receive recommendations.")
        if not preferences or not preferences.timezone:
            gaps.append("Timezone is unknown; dates use UTC until you save a location.")
        start = datetime.combine(today, time.min, zone)
        end = datetime.combine(today + timedelta(days=days), time.min, zone)
        events = CalendarRepository(self.session).list_events(
            user_id, start, end, include_hidden=False
        )
        contexts = []
        for offset in range(days):
            day = today + timedelta(days=offset)
            when = datetime.combine(day, time(9), zone)
            context = self._context(user_id, when, source="day", key=f"day:{day}")
            if (
                context.high_celsius is None
                and "Weather unavailable; weather scoring is neutral." not in gaps
            ):
                gaps.append("Weather unavailable; weather scoring is neutral.")
            contexts.append(context)
            signatures: set[tuple[str, str | None, str | None, str]] = set()
            for event, _, _ in events:
                event_day = (
                    aware(event.starts_at).date()
                    if event.is_all_day
                    else aware(event.starts_at).astimezone(zone).date()
                )
                if event_day != day:
                    continue
                event_when = when if event.is_all_day else aware(event.starts_at)
                event_context = self._context(
                    user_id, event_when, source="event", key=f"event:{event.id}"
                )
                event_context = RecommendationContext.model_validate(
                    {
                        **event_context.model_dump(),
                        "calendar_event_id": event.id,
                        "occasion": event.event_type,
                        "formality": event.formality,
                        "setting": event.setting,
                    }
                )
                signature = (
                    event.event_type,
                    event.formality,
                    event.setting,
                    event_context.daypart,
                )
                if signature not in signatures:
                    contexts.append(event_context)
                    signatures.add(signature)
        recommendations: list[WearRecommendationResponse] = []
        planned: dict[UUID, date] = {}
        for context in contexts if owned else []:
            recommendation = self._generate(user_id, context, owned, planned)
            recommendations.append(recommendation)
            if context.source == "day":
                # Rotate across the plan: today's pick (and blend members) rest on later days.
                members = (
                    [item.fragrance.id for item in recommendation.blend.items]
                    if recommendation.blend
                    else [recommendation.fragrance.id]
                )
                for member in members:
                    planned.setdefault(member, context.local_date)
        return WearRecommendationPlan(
            timezone=str(zone), local_date=today, recommendations=recommendations, gaps=gaps
        )

    def today(self, user_id: UUID) -> WearRecommendationPlan:
        return self._plan(user_id, 1)

    def week(self, user_id: UUID) -> WearRecommendationPlan:
        return self._plan(user_id, 7)

    def preview(
        self, user_id: UUID, request: RecommendationPreviewRequest
    ) -> WearRecommendationResponse:
        owned = self._owned(user_id)
        if not owned:
            raise unprocessable("collection_required", "Add an owned fragrance first")
        when = request.recommended_for or self.clock().replace(second=0, microsecond=0)
        payload = request.model_dump(mode="json")
        payload["recommended_for"] = when.isoformat()
        key = (
            "manual:"
            + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:32]
        )
        context = self._context(user_id, when, source=request.source, key=key)
        changes = request.model_dump(exclude_none=True, exclude={"recommended_for", "source"})
        context = RecommendationContext.model_validate({**context.model_dump(), **changes})
        return self._generate(user_id, context, owned, {})

    def _inputs(
        self,
        user_id: UUID,
        context: RecommendationContext,
        owned: list[UserCollectionItem],
        planned: dict[UUID, date] | None = None,
    ) -> list[tuple[UserCollectionItem, CandidateInput]]:
        reference_time = max(context.recommended_for, self.clock())
        # Bounded historical window, loaded once per context rather than per candidate.
        histories = list(
            self.session.execute(
                select(WearLog, WearFeedback, UserCollectionItem.fragrance_id)
                .join(UserCollectionItem, UserCollectionItem.id == WearLog.collection_item_id)
                .outerjoin(WearFeedback, WearFeedback.wear_log_id == WearLog.id)
                .where(
                    WearLog.user_id == user_id,
                    WearLog.worn_at <= reference_time,
                    WearLog.worn_at >= reference_time - timedelta(days=365),
                )
            )
        )
        rejects = list(
            self.session.execute(
                select(Recommendation.fragrance_id, Recommendation.context_data)
                .join(
                    RecommendationDecision,
                    RecommendationDecision.recommendation_id == Recommendation.id,
                )
                .where(
                    Recommendation.user_id == user_id,
                    RecommendationDecision.user_id == user_id,
                    RecommendationDecision.action == "rejected",
                    Recommendation.recommended_for >= reference_time - timedelta(days=30),
                )
            )
        )
        taste = TasteProfileService(self.session).affinities(user_id)
        # Exploration derives from wear history (stable per input), never from generated
        # recommendations, so regenerating the same plan stays idempotent.
        shown: dict[UUID, int] = {}
        for wear, _, fid in histories:
            if aware(wear.worn_at) >= reference_time - timedelta(days=90):
                shown[fid] = shown.get(fid, 0) + 1
        total_shown = sum(shown.values())
        inputs = []
        for item in owned:
            fragrance = item.fragrance
            rows = [(wear, feedback) for wear, feedback, fid in histories if fid == fragrance.id]
            ratings = [
                feedback.rating
                for _, feedback in rows
                if feedback is not None and feedback.rating is not None
            ]
            same = [
                feedback.rating if feedback is not None and feedback.rating is not None else 3
                for wear, feedback in rows
                if context.occasion is not None and wear.occasion == context.occasion
            ]
            community = fragrance.community
            recent = max((aware(wear.worn_at) for wear, _ in rows), default=None)
            inputs.append(
                (
                    item,
                    CandidateInput(
                        fragrance_id=fragrance.id,
                        projection=item.custom_projection or fragrance.projection_level,
                        longevity=float(
                            item.custom_longevity
                            if item.custom_longevity is not None
                            else (fragrance.longevity_score or Decimal(0))
                        )
                        if item.custom_longevity is not None
                        or fragrance.longevity_score is not None
                        else None,
                        season_weights={
                            link.season: float(link.weight) for link in fragrance.seasons
                        },
                        occasion_weights={
                            link.occasion: float(link.weight) for link in fragrance.occasions
                        },
                        day_votes=community.day_votes if community else None,
                        night_votes=community.night_votes if community else None,
                        rating=item.user_rating,
                        feedback_rating=sum(ratings) / len(ratings) if ratings else None,
                        occasion_history_rating=sum(same) / len(same) if same else None,
                        days_since_wear=self._rest_days(
                            float(int((reference_time - recent).total_seconds() / 86400))
                            if recent
                            else None,
                            planned,
                            fragrance.id,
                            context,
                        ),
                        taste=round(taste_affinity(taste, signals(fragrance)), 4)
                        if taste
                        else None,
                        exploration=round(
                            exploration_bonus(shown.get(fragrance.id, 0), total_shown) * 100, 2
                        ),
                        wears_last_30_days=sum(
                            1
                            for wear, _ in rows
                            if aware(wear.worn_at) >= reference_time - timedelta(days=30)
                        ),
                        rejections=sum(
                            1
                            for fid, data in rejects
                            if fid == fragrance.id and data.get("occasion") == context.occasion
                        ),
                    ),
                )
            )
        return inputs

    @staticmethod
    def _rest_days(
        days: float | None,
        planned: dict[UUID, date] | None,
        fragrance_id: UUID,
        context: RecommendationContext,
    ) -> float | None:
        """Days since worn, also counting a pick planned earlier in the same plan."""
        if planned and fragrance_id in planned:
            gap = float((context.local_date - planned[fragrance_id]).days)
            if gap >= 0:
                return gap if days is None else min(days, gap)
        return days

    def _blend_candidates(
        self,
        user_id: UUID,
        context: RecommendationContext,
        singles: dict[UUID, tuple[float, CandidateInput]],
        best_single: float,
    ) -> list[tuple[LayeringStackSuggestion, float]]:
        """Top owned blends, scored on the blend itself and on how well each member fits today."""
        from scentiq_api.repositories.layering import LayeringRepository
        from scentiq_api.services.layering import LayeringService

        service = LayeringService(LayeringRepository(self.session))
        suggestions = service.stack_suggestions(
            user_id,
            goal=cast(LayeringGoal, blend_goal(context)),
            limit=6,
            stack_size=None,
        )
        results: list[tuple[LayeringStackSuggestion, float]] = []
        for stack in suggestions:
            ids = [item.fragrance.id for item in stack.items]
            if not all(item in singles for item in ids):
                continue
            member_fit = mean(singles[item][0] for item in ids)
            rest_values = [
                value for item in ids if (value := singles[item][1].days_since_wear) is not None
            ]
            rested = min(rest_values) if rest_values else None
            score = 0.5 * stack.score_percent + 0.5 * member_fit
            if rested is not None and rested < 1:
                score -= 10
            if score >= best_single - BLEND_WINDOW:
                results.append((stack, round(max(0.0, min(100.0, score)), 2)))
        results.sort(key=lambda pair: (-pair[1], tuple(str(i.fragrance.id) for i in pair[0].items)))
        return results[:MAX_BLENDS]

    def _generate(
        self,
        user_id: UUID,
        context: RecommendationContext,
        owned: list[UserCollectionItem],
        planned: dict[UUID, date] | None = None,
    ) -> WearRecommendationResponse:
        started = timer.monotonic()
        preferences = self._preferences(user_id)
        inputs = self._inputs(user_id, context, owned, planned)
        weights = TasteProfileService(self.session).component_weights(user_id)
        taste_record = self.session.get(UserTasteProfile, user_id)
        taste_events = taste_record.event_count if taste_record else 0
        pref = {
            key: getattr(preferences, key) if preferences else None
            for key in (
                "preferred_projection",
                "preferred_longevity",
                "maximum_sprays",
                "preferred_occasion",
                "preferred_season",
            )
        }
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "context": context.model_dump(mode="json"),
                    "preferences": pref,
                    "algorithm": WEAR_ALGORITHM_VERSION,
                    "weights": weights,
                    "taste_events": taste_events,
                    "candidates": [
                        {
                            "item": str(item.id),
                            "name": item.fragrance.name,
                            "status": item.status,
                            "input": candidate.model_dump(mode="json"),
                        }
                        for item, candidate in inputs
                    ],
                },
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode()
        ).hexdigest()
        statement = select(Recommendation).where(
            Recommendation.user_id == user_id,
            Recommendation.context_key == context.context_key,
            Recommendation.input_fingerprint == fingerprint,
            Recommendation.algorithm_version == WEAR_ALGORITHM_VERSION,
        )
        existing = self.session.scalar(statement)
        if existing is not None:
            return self._response(user_id, existing)
        # Learning shifts scores after every decision. A pick the user already accepted or
        # replaced stays visible for its context rather than being regenerated underneath
        # them; actually wearing it still refreshes the plan (rotation changes by design).
        decided = self.session.scalar(
            select(Recommendation)
            .join(
                RecommendationDecision,
                RecommendationDecision.recommendation_id == Recommendation.id,
            )
            .where(
                Recommendation.user_id == user_id,
                Recommendation.context_key == context.context_key,
                Recommendation.algorithm_version == WEAR_ALGORITHM_VERSION,
                RecommendationDecision.action.in_(("accepted", "replaced")),
                ~select(WearLog.id).where(WearLog.recommendation_id == Recommendation.id).exists(),
            )
            .order_by(Recommendation.created_at.desc())
            .limit(1)
        )
        if decided is not None:
            return self._response(user_id, decided)
        scores = [
            (
                item,
                score_candidate(
                    candidate,
                    context,
                    maximum_sprays=preferences.maximum_sprays if preferences else None,
                    preferred_projection=preferences.preferred_projection if preferences else None,
                    preferred_longevity=float(preferences.preferred_longevity)
                    if preferences and preferences.preferred_longevity is not None
                    else None,
                    component_weights=weights,
                ),
            )
            for item, candidate in inputs
        ]
        scores.sort(
            key=lambda pair: (
                -pair[1].score,
                pair[0].fragrance.name.casefold(),
                str(pair[0].fragrance_id),
                str(pair[0].id),
            )
        )
        # A fragrance may have a bottle and a decant. Rank the fragrance once.
        inputs_by_item = {item.id: candidate for item, candidate in inputs}
        distinct = []
        seen: set[UUID] = set()
        for pair in scores:
            if pair[0].fragrance_id not in seen:
                distinct.append(pair)
                seen.add(pair[0].fragrance_id)
        singles = {
            candidate_item.fragrance_id: (score.score, inputs_by_item[candidate_item.id])
            for candidate_item, score in distinct
        }
        entries: list[dict[str, Any]] = [
            {
                "fragrance_id": candidate_item.fragrance_id,
                "name": candidate_item.fragrance.name.casefold(),
                "blend_key": "",
                "score": score.score,
                "components": score.components,
                "guidance": {
                    "recommended_sprays": score.sprays,
                    "evidence_coverage": score.evidence_coverage,
                    "reasons": score.reasons,
                    "warnings": score.warnings,
                },
            }
            for candidate_item, score in distinct
        ]
        for stack, blend_score in self._blend_candidates(
            user_id, context, singles, distinct[0][1].score
        ):
            members = [item.fragrance.name for item in stack.items]
            entries.append(
                {
                    "fragrance_id": stack.items[0].fragrance.id,
                    "name": " + ".join(item.fragrance.name.casefold() for item in stack.items),
                    "blend_key": blend_key_for([item.fragrance.id for item in stack.items]),
                    "score": blend_score,
                    "components": {
                        "blend": float(stack.score_percent),
                        "members": round(mean(singles[i.fragrance.id][0] for i in stack.items), 2),
                        "known_pairing": round(stack.score_components.known_pairing * 100, 2),
                    },
                    "guidance": {
                        "recommended_sprays": max(1, stack.total_sprays),
                        "evidence_coverage": stack.evidence_coverage,
                        "reasons": [
                            f"Blend of {len(members)} scents: " + " + ".join(members),
                            *stack.pairing_evidence[:1],
                            *stack.reasons[:1],
                        ][:3],
                        "warnings": stack.warnings[:2],
                        "blend": stack.model_dump(mode="json"),
                    },
                }
            )
        entries.sort(
            key=lambda entry: (
                -float(str(entry["score"])),
                bool(entry["blend_key"]),  # a single wins an exact tie with a blend
                str(entry["name"]),
                str(entry["fragrance_id"]),
            )
        )
        top = entries[:6]
        best = top[0]
        best_guidance: dict[str, Any] = best["guidance"]
        record = Recommendation(
            user_id=user_id,
            recommended_for=context.recommended_for,
            context=context.occasion or "open_day",
            context_key=context.context_key,
            calendar_event_id=context.calendar_event_id,
            input_fingerprint=fingerprint,
            context_data=context.model_dump(mode="json"),
            fragrance_id=best["fragrance_id"],
            score=Decimal(str(best["score"])),
            score_components=best["components"],
            evidence_coverage=best_guidance["evidence_coverage"],
            recommended_sprays=best_guidance["recommended_sprays"],
            reasons=best_guidance["reasons"],
            warnings=best_guidance["warnings"],
            algorithm_version=WEAR_ALGORITHM_VERSION,
        )
        try:
            with self.session.begin_nested():
                self.session.add(record)
                self.session.flush()
                for rank, entry in enumerate(top, 1):
                    self.session.add(
                        RecommendationCandidate(
                            recommendation_id=record.id,
                            fragrance_id=entry["fragrance_id"],
                            blend_key=entry["blend_key"],
                            rank=rank,
                            score=Decimal(str(entry["score"])),
                            score_components=entry["components"],
                            guidance=entry["guidance"],
                        )
                    )
                self.session.flush()
        except IntegrityError:
            existing = self.session.scalar(statement)
            if existing is None:
                raise
            return self._response(user_id, existing)
        diagnostic_logger.info(
            format_runtime_event(
                "wear_recommendation_generated",
                "INFO",
                algorithm_version=WEAR_ALGORITHM_VERSION,
                context_type=context.source,
                candidate_count=len(top),
                selected_fragrance_id=str(record.fragrance_id),
                score=float(record.score),
                evidence_coverage=record.evidence_coverage,
                elapsed_ms=round((timer.monotonic() - started) * 1000),
            )
        )
        return self._response(user_id, record)

    def get(self, user_id: UUID, recommendation_id: UUID, *, lock: bool = False) -> Recommendation:
        statement = select(Recommendation).where(
            Recommendation.id == recommendation_id, Recommendation.user_id == user_id
        )
        if lock:
            statement = statement.with_for_update()
        record = self.session.scalar(statement)
        if record is None:
            raise not_found("Recommendation not found")
        return record

    def _response(self, user_id: UUID, record: Recommendation) -> WearRecommendationResponse:
        candidates = list(
            self.session.execute(
                select(RecommendationCandidate, Fragrance)
                .join(Fragrance, Fragrance.id == RecommendationCandidate.fragrance_id)
                .where(RecommendationCandidate.recommendation_id == record.id)
                .options(
                    joinedload(Fragrance.brand),
                    selectinload(Fragrance.accord_links).joinedload(FragranceAccord.accord),
                )
                .order_by(RecommendationCandidate.rank)
            )
        )
        results = [
            WearRecommendationCandidate.model_validate(
                {
                    "fragrance": to_fragrance_summary(fragrance),
                    "score": float(candidate.score),
                    "score_components": candidate.score_components,
                    "blend_key": candidate.blend_key,
                    **candidate.guidance,
                }
            )
            for candidate, fragrance in candidates
        ]
        decision = self.session.scalar(
            select(RecommendationDecision).where(
                RecommendationDecision.user_id == user_id,
                RecommendationDecision.recommendation_id == record.id,
            )
        )
        return WearRecommendationResponse(
            **results[0].model_dump(),
            id=record.id,
            context_key=record.context_key or "legacy",
            recommended_for=aware(record.recommended_for),
            context=RecommendationContext.model_validate(record.context_data),
            algorithm_version=record.algorithm_version,
            alternatives=results[1:],
            decision=RecommendationDecisionResponse.model_validate(
                {"action": decision.action, "selected_fragrance_id": decision.selected_fragrance_id}
            )
            if decision
            else None,
        )

    def decide(
        self, user_id: UUID, recommendation_id: UUID, request: RecommendationDecisionRequest
    ) -> RecommendationDecisionResponse:
        record = self.get(user_id, recommendation_id, lock=True)
        selected = request.selected_fragrance_id
        if request.action == "replaced" and selected is None:
            raise unprocessable("fragrance_required", "Choose your replacement fragrance")
        if request.action == "accepted":
            selected = selected or record.fragrance_id
            if selected != record.fragrance_id:
                raise unprocessable(
                    "replacement_required", "Use replaced for an alternative fragrance"
                )
        if selected is not None and not any(
            item.fragrance_id == selected for item in self._owned(user_id)
        ):
            raise not_found("Owned fragrance not found")
        statement = select(RecommendationDecision).where(
            RecommendationDecision.user_id == user_id,
            RecommendationDecision.recommendation_id == record.id,
        )
        decision = self.session.scalar(statement)
        if decision is None:
            decision = RecommendationDecision(
                user_id=user_id, recommendation_id=record.id, action=request.action
            )
            self.session.add(decision)
        decision.action = request.action
        decision.selected_fragrance_id = selected
        self.session.flush()
        self._learn(user_id, record, request.action, selected, request.blend_key)
        return RecommendationDecisionResponse(action=request.action, selected_fragrance_id=selected)

    def _candidate_fragrances(
        self, user_id: UUID, candidate: RecommendationCandidate
    ) -> list[Fragrance]:
        """The owned fragrances a candidate stands for: one scent, or every blend member."""
        blend = candidate.guidance.get("blend")
        wanted = (
            {UUID(str(item["fragrance"]["id"])) for item in blend["items"]}
            if isinstance(blend, dict)
            else {candidate.fragrance_id}
        )
        return [item.fragrance for item in self._owned(user_id) if item.fragrance_id in wanted]

    def _learn(
        self,
        user_id: UUID,
        record: Recommendation,
        action: str,
        selected: UUID | None,
        blend_key: str,
    ) -> None:
        """Feed a decision into the taste profile and the learned component weights."""
        candidates = list(
            self.session.scalars(
                select(RecommendationCandidate)
                .where(RecommendationCandidate.recommendation_id == record.id)
                .order_by(RecommendationCandidate.rank)
            )
        )
        if not candidates:
            return
        top = candidates[0]
        target_key = blend_key
        if action == "accepted" and not target_key:
            target_key = top.blend_key  # accepting the recommendation accepts what it shows
        chosen = next(
            (
                candidate
                for candidate in candidates
                if candidate.fragrance_id == (selected or record.fragrance_id)
                and candidate.blend_key == target_key
            ),
            None,
        )
        taste = TasteProfileService(self.session)

        def feedback(candidate: RecommendationCandidate, strength: float, accepted: bool) -> None:
            fragrances = self._candidate_fragrances(user_id, candidate)
            components = None
            if not candidate.blend_key:
                components = {
                    key: max(0.0, min(1.0, candidate.score_components.get(key, 0) / maximum))
                    for key, maximum in COMPONENT_MAXIMUM.items()
                }
            taste.learn(
                user_id,
                [signals(item) for item in fragrances],
                strength,
                components=components,
                accepted=accepted if components is not None else None,
            )
            self.session.add(
                InteractionEvent(
                    user_id=user_id,
                    event_type="accept" if accepted else "reject",
                    subject_type="stack" if candidate.blend_key else "recommendation",
                    fragrance_ids=[str(item.id) for item in fragrances],
                    context={"source": record.context[:30], "action": action},
                )
            )

        if action in ("accepted", "replaced") and chosen is not None:
            feedback(chosen, polarity("accept"), True)
            if action == "replaced" and chosen is not top:
                feedback(top, polarity("skip"), False)
        elif action == "rejected":
            feedback(top, polarity("reject"), False)
        elif action == "dismissed":
            feedback(top, polarity("dismiss"), False)

    def wear(
        self, user_id: UUID, recommendation_id: UUID, request: RecommendationWearRequest
    ) -> WearLogResponse:
        record = self.get(user_id, recommendation_id)
        selected = request.selected_fragrance_id or record.fragrance_id
        item = next((item for item in self._owned(user_id) if item.fragrance_id == selected), None)
        if item is None:
            raise not_found("Owned fragrance not found")
        context = RecommendationContext.model_validate(record.context_data)
        guidance = self.session.scalar(
            select(RecommendationCandidate).where(
                RecommendationCandidate.recommendation_id == record.id,
                RecommendationCandidate.fragrance_id == selected,
                RecommendationCandidate.blend_key == request.blend_key,
            )
        )
        sprays = request.sprays or (
            int(str(guidance.guidance["recommended_sprays"]))
            if guidance
            else record.recommended_sprays
        )
        entry = WearLog(
            user_id=user_id,
            collection_item_id=item.id,
            recommendation_id=record.id,
            worn_at=request.worn_at or self.clock(),
            sprays=sprays,
            occasion=request.occasion or context.occasion,
            setting=request.setting or context.setting,
            notes=request.notes,
        )
        self.session.add(entry)
        # Wearing a blend logs every member, each with its own spray count.
        blend = guidance.guidance.get("blend") if guidance and request.blend_key else None
        if isinstance(blend, dict):
            owned_by_fragrance = {owned.fragrance_id: owned for owned in self._owned(user_id)}
            for blend_item in blend["items"]:
                member_id = UUID(str(blend_item["fragrance"]["id"]))
                member = owned_by_fragrance.get(member_id)
                if member is None or member.id == item.id:
                    if member is not None:
                        entry.sprays = int(blend_item["suggested_sprays"])
                    continue
                self.session.add(
                    WearLog(
                        user_id=user_id,
                        collection_item_id=member.id,
                        recommendation_id=record.id,
                        worn_at=entry.worn_at,
                        sprays=int(blend_item["suggested_sprays"]),
                        occasion=entry.occasion,
                        setting=entry.setting,
                        notes=request.notes,
                    )
                )
        self.session.flush()
        self.decide(
            user_id,
            record.id,
            RecommendationDecisionRequest(
                action="accepted" if selected == record.fragrance_id else "replaced",
                selected_fragrance_id=selected,
                blend_key=request.blend_key,
            ),
        )
        return WearLogResponse(
            id=entry.id,
            collection_item_id=item.id,
            fragrance_id=selected,
            fragrance_name=item.fragrance.name,
            brand_name=item.fragrance.brand.name,
            worn_at=entry.worn_at,
            sprays=entry.sprays,
            occasion=entry.occasion,
            setting=entry.setting,
            notes=entry.notes,
            recommendation_id=record.id,
        )
