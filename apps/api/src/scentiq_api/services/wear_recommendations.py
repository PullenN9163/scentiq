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
    CalendarEvent,
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
from scentiq_api.models.recommendation_choices import RecommendationFeedback
from scentiq_api.repositories.calendar import CalendarRepository
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
from scentiq_api.services.ai_ranking import ranking_configuration_version
from scentiq_api.services.fragrances import to_fragrance_summary
from scentiq_api.services.personalized_ranking import rerank
from scentiq_api.services.recommendation_choices import RecommendationChoiceService
from scentiq_api.services.taste_profile import TasteProfileService
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
                    joinedload(UserCollectionItem.fragrance).selectinload(Fragrance.note_links),
                    joinedload(UserCollectionItem.fragrance)
                    .selectinload(Fragrance.accord_links)
                    .joinedload(FragranceAccord.accord),
                )
                .order_by(UserCollectionItem.created_at, UserCollectionItem.id)
            )
        )

    def _context(
        self,
        user_id: UUID,
        when: datetime,
        *,
        source: str,
        key: str,
        duration_minutes: int | None = None,
    ) -> RecommendationContext:
        from scentiq_api.services.recommendation_context import RecommendationContextBuilder

        return RecommendationContext.model_validate(
            RecommendationContextBuilder(self.session, clock=self.clock).build(
                user_id, when, source=source, key=key, duration_minutes=duration_minutes
            )
        )

    def _plan(self, user_id: UUID, days: int) -> WearRecommendationPlan:
        preferences = self._preferences(user_id)
        zone = self._zone(preferences)
        today = self.clock().astimezone(zone).date()
        owned = self._owned(user_id)
        profile = TasteProfileService(self.session).for_user(user_id)
        owned = [item for item in owned if item.fragrance_id not in profile.excluded_ids]
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
            # Stable hour buckets refresh Today without changing every reload.
            when = (
                self.clock().astimezone(zone).replace(minute=0, second=0, microsecond=0)
                if offset == 0
                else datetime.combine(day, time(9), zone)
            )
            context = self._context(user_id, when, source="day", key=f"day:{day}")
            day_start = datetime.combine(day, time.min, zone)
            day_end = datetime.combine(day + timedelta(days=1), time.min, zone)

            def overlaps_day(
                event: CalendarEvent,
                day: date = day,
                day_start: datetime = day_start,
                day_end: datetime = day_end,
            ) -> bool:
                if event.is_all_day:
                    return aware(event.starts_at).date() <= day < aware(event.ends_at).date()
                return aware(event.starts_at) < day_end and aware(event.ends_at) > day_start

            def event_window(
                event: CalendarEvent,
                when: datetime = when,
                day_end: datetime = day_end,
                day_start: datetime = day_start,
                offset: int = offset,
            ) -> tuple[datetime, int]:
                if event.is_all_day:
                    target = when
                    ending = day_end
                else:
                    target = max(aware(event.starts_at), self.clock() if offset == 0 else day_start)
                    target = target.replace(second=0, microsecond=0)
                    ending = aware(event.ends_at)
                return target, min(
                    31 * 24 * 60, max(1, int((ending - target).total_seconds() / 60))
                )

            relevant_events = sorted(
                [
                    event
                    for event, _, _ in events
                    if overlaps_day(event)
                    and (event.is_all_day or offset > 0 or aware(event.ends_at) > self.clock())
                ],
                key=lambda event: aware(event.starts_at),
            )
            if relevant_events:
                primary_event = relevant_events[0]
                target, duration = event_window(primary_event)
                context = self._context(
                    user_id, target, source="day", key=f"day:{day}", duration_minutes=duration
                )
                context = context.model_copy(
                    update={
                        "occasion": primary_event.event_type,
                        "formality": primary_event.formality,
                        "setting": primary_event.setting,
                        "calendar_event_id": primary_event.id,
                    }
                )
            if (
                context.high_celsius is None
                and "Weather unavailable; weather scoring is neutral." not in gaps
            ):
                gaps.append("Weather unavailable; weather scoring is neutral.")
            contexts.append(context)
            signatures: set[tuple[str, str | None, str | None, str]] = set()
            for event, _, _ in events:
                if not overlaps_day(event) or (
                    offset == 0 and not event.is_all_day and aware(event.ends_at) <= self.clock()
                ):
                    continue
                event_when, duration = event_window(event)
                event_context = self._context(
                    user_id,
                    event_when,
                    source="event",
                    key=f"event:{event.id}:{day}",
                    duration_minutes=duration,
                )
                event_context = event_context.model_copy(
                    update={
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
        recommendations = []
        planned: dict[UUID, int] = {}
        for context in contexts if owned else []:
            # Accepted selections are stable even when context inputs are refreshed.
            accepted = self.session.scalar(
                select(Recommendation)
                .join(
                    RecommendationDecision,
                    RecommendationDecision.recommendation_id == Recommendation.id,
                )
                .where(
                    Recommendation.user_id == user_id,
                    Recommendation.context_key == context.context_key,
                    ~select(WearLog.id)
                    .where(WearLog.recommendation_id == Recommendation.id)
                    .exists(),
                    RecommendationDecision.action.in_(("accepted", "replaced")),
                    RecommendationDecision.selected_fragrance_id.in_(
                        [item.fragrance_id for item in owned]
                    ),
                )
                .order_by(Recommendation.created_at.desc())
                .limit(1)
            )
            if accepted:
                response = self._response(user_id, accepted)
            if not accepted:
                response = self._generate(
                    user_id, context, owned, planned=planned if days > 1 else None
                )
            recommendations.append(response)
            planned[response.fragrance.id] = planned.get(response.fragrance.id, 0) + 1
        if (
            days > 1
            and recommendations
            and len({row.fragrance.id for row in recommendations}) < len(recommendations)
        ):
            gaps.append(
                "Some fragrances repeat to balance your collection size and contextual fit."
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
        profile = TasteProfileService(self.session).for_user(user_id)
        owned = [
            item for item in self._owned(user_id) if item.fragrance_id not in profile.excluded_ids
        ]
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
        strong_feedback = set(
            self.session.scalars(
                select(RecommendationFeedback.fragrance_id).where(
                    RecommendationFeedback.user_id == user_id,
                    RecommendationFeedback.reason == "too_strong",
                )
            )
        )
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
                        too_strong_count=int(fragrance.id in strong_feedback),
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
        self,
        user_id: UUID,
        context: RecommendationContext,
        owned: list[UserCollectionItem],
        *,
        planned: dict[UUID, int] | None = None,
    ) -> WearRecommendationResponse:
        started = timer.monotonic()
        preferences = self._preferences(user_id)
        profile = TasteProfileService(self.session).for_user(user_id)
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
        surface = "week" if planned is not None else "today"
        fingerprint_context = context.model_dump(mode="json")
        fingerprint_context["recommended_for"] = context.recommended_for.replace(
            minute=0, second=0, microsecond=0
        ).isoformat()
        if context.duration_minutes:
            fingerprint_context["duration_minutes"] = ((context.duration_minutes + 59) // 60) * 60
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "context": fingerprint_context,
                    "preferences": pref,
                    "algorithm": WEAR_ALGORITHM_VERSION,
                    "taste_version": profile.version,
                    "ranking_config": ranking_configuration_version(surface),
                    "planned": {str(key): value for key, value in (planned or {}).items()},
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
        for item, score in scores:
            taste = round(8 * profile.affinity(item.fragrance), 2)
            diversity = -(
                0
                if profile.variety == "familiar"
                else 18
                if profile.variety == "adventurous"
                else 12
            ) * (planned or {}).get(item.fragrance_id, 0)
            score.components.update(taste_affinity=taste, planned_rotation=float(diversity))
            score.score = round(max(0, min(100, score.score + taste + diversity)), 2)
            if taste > 0:
                score.reasons = [
                    "Fits your explicit preferences and rated scent profile",
                    *score.reasons,
                ][:3]
            elif taste < 0:
                score.warnings.append("Some profile signals conflict with your recorded taste.")
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
        ranking = rerank(
            self.session,
            user_id,
            surface=surface,
            candidates=[
                {
                    "candidate_id": str(item.fragrance_id),
                    "baseline_score": score.score,
                    "evidence": {
                        "name": item.fragrance.name,
                        "reasons": score.reasons,
                        "warnings": score.warnings,
                        "components": score.components,
                        "taste_fit": profile.affinity(item.fragrance),
                    },
                }
                for item, score in distinct
            ],
            context={
                **context.model_dump(mode="json"),
                "taste_features": profile.features,
                "variety_preference": profile.variety,
            },
            version=profile.version,
        )
        by_id = {str(item.fragrance_id): (item, score) for item, score in distinct}
        distinct = [by_id[key] for key in ranking.ordered_ids]
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
                for rank, (candidate_item, score) in enumerate(distinct, 1):
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
                                "generation_mode": ranking.generation_mode,
                                "model_version": ranking.model_version,
                                "profile_version": profile.version,
                                "ai_reasons": ranking.explanations.get(
                                    str(candidate_item.fragrance_id), []
                                ),
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
                generation_mode=ranking.generation_mode,
                planned_repeat=bool((planned or {}).get(record.fragrance_id, 0)),
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
        response = WearRecommendationResponse(
            **results[0].model_dump(),
            id=record.id,
            canonical_fragrance_id=record.fragrance_id,
            generation_mode=str(candidates[0][0].guidance.get("generation_mode", "baseline")),
            model_version=candidates[0][0].guidance.get("model_version"),
            profile_version=candidates[0][0].guidance.get("profile_version"),
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
        return RecommendationChoiceService(self.session).current(user_id, response)

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
        if selected is not None:
            allowed = self.session.scalar(
                select(RecommendationCandidate.id).where(
                    RecommendationCandidate.recommendation_id == recommendation_id,
                    RecommendationCandidate.fragrance_id == selected,
                )
            )
            profile = TasteProfileService(self.session).for_user(user_id)
            if allowed is None or selected in profile.excluded_ids:
                raise unprocessable(
                    "batch_changed", "Refresh recommendations before choosing this fragrance"
                )
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
        if selected is not None and request.action in {"accepted", "replaced"}:
            from scentiq_api.models.recommendation_choices import RecommendationChoice

            choice = self.session.get(RecommendationChoice, recommendation_id)
            if choice is None:
                choice = RecommendationChoice(
                    recommendation_id=recommendation_id,
                    selected_fragrance_id=selected,
                    seen_ids=list(dict.fromkeys([str(record.fragrance_id), str(selected)])),
                )
                self.session.add(choice)
            else:
                choice.selected_fragrance_id = selected
                choice.seen_ids = list(dict.fromkeys([*choice.seen_ids, str(selected)]))
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
