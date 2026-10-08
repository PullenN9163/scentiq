"""One authoritative wear engine for Today, Week, manual previews and Agent tools."""

import hashlib
import json
import time as timer
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
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
    Recommendation,
    RecommendationCandidate,
    RecommendationDecision,
    UserCollectionItem,
    UserPreference,
    WearFeedback,
    WearLog,
)
from scentiq_api.repositories.calendar import CalendarRepository
from scentiq_api.repositories.weather import WeatherRepository
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
from scentiq_api.services.wear_scoring import (
    WEAR_ALGORITHM_VERSION,
    CandidateInput,
    score_candidate,
)


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
        recommendations = (
            [self._generate(user_id, context, owned) for context in contexts] if owned else []
        )
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
        return self._generate(user_id, context, owned)

    def _inputs(
        self, user_id: UUID, context: RecommendationContext, owned: list[UserCollectionItem]
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
                        days_since_wear=float(
                            int((reference_time - recent).total_seconds() / 86400)
                        )
                        if recent
                        else None,
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

    def _generate(
        self, user_id: UUID, context: RecommendationContext, owned: list[UserCollectionItem]
    ) -> WearRecommendationResponse:
        started = timer.monotonic()
        preferences = self._preferences(user_id)
        inputs = self._inputs(user_id, context, owned)
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
        distinct = []
        seen: set[UUID] = set()
        for pair in scores:
            if pair[0].fragrance_id not in seen:
                distinct.append(pair)
                seen.add(pair[0].fragrance_id)
        item, best = distinct[0]
        record = Recommendation(
            user_id=user_id,
            recommended_for=context.recommended_for,
            context=context.occasion or "open_day",
            context_key=context.context_key,
            calendar_event_id=context.calendar_event_id,
            input_fingerprint=fingerprint,
            context_data=context.model_dump(mode="json"),
            fragrance_id=item.fragrance_id,
            score=Decimal(str(best.score)),
            score_components=best.components,
            evidence_coverage=best.evidence_coverage,
            recommended_sprays=best.sprays,
            reasons=best.reasons,
            warnings=best.warnings,
            algorithm_version=WEAR_ALGORITHM_VERSION,
        )
        try:
            with self.session.begin_nested():
                self.session.add(record)
                self.session.flush()
                for rank, (candidate_item, score) in enumerate(distinct[:6], 1):
                    self.session.add(
                        RecommendationCandidate(
                            recommendation_id=record.id,
                            fragrance_id=candidate_item.fragrance_id,
                            rank=rank,
                            score=Decimal(str(score.score)),
                            score_components=score.components,
                            guidance={
                                "recommended_sprays": score.sprays,
                                "evidence_coverage": score.evidence_coverage,
                                "reasons": score.reasons,
                                "warnings": score.warnings,
                            },
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
                candidate_count=len(distinct),
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
        return RecommendationDecisionResponse(action=request.action, selected_fragrance_id=selected)

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
        self.session.flush()
        self.decide(
            user_id,
            record.id,
            RecommendationDecisionRequest(
                action="accepted" if selected == record.fragrance_id else "replaced",
                selected_fragrance_id=selected,
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
