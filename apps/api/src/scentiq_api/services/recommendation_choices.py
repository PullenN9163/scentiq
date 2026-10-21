"""Stable displayed selections; recommendation row locks serialize advances in PostgreSQL."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from scentiq_api.errors import conflict, not_found
from scentiq_api.models import UserCollectionItem
from scentiq_api.models.recommendation_choices import (
    RecommendationChoice,
    RecommendationChoiceReceipt,
    RecommendationFeedback,
)
from scentiq_api.schemas.wear_recommendations import (
    RecommendationFeedbackRequest,
    RecommendationFeedbackResponse,
    RecommendationNextRequest,
    WearRecommendationResponse,
)


class RecommendationChoiceService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def current(
        self, user_id: UUID, response: WearRecommendationResponse
    ) -> WearRecommendationResponse:
        owned = set(
            self.session.scalars(
                select(UserCollectionItem.fragrance_id).where(
                    UserCollectionItem.user_id == user_id, UserCollectionItem.status == "owned"
                )
            )
        )
        from scentiq_api.services.taste_profile import TasteProfileService

        owned -= TasteProfileService(self.session).for_user(user_id).excluded_ids
        candidates = {
            candidate.fragrance.id: candidate
            for candidate in [response, *response.alternatives]
            if candidate.fragrance.id in owned
        }
        if not candidates:
            raise conflict(
                "recommendation_changed",
                "Refresh recommendations for your updated collection or preferences",
            )
        state = self.session.get(RecommendationChoice, response.id)
        selected_id: UUID | None = state.selected_fragrance_id if state else response.fragrance.id
        accepted = response.decision
        if accepted and accepted.action in {"accepted", "replaced"}:
            selected_id = accepted.selected_fragrance_id
        if selected_id is None or selected_id not in candidates:
            raise conflict(
                "recommendation_changed",
                "Refresh recommendations for your updated collection or preferences",
            )
        selected = candidates[selected_id]
        seen = set(state.seen_ids) if state else {str(selected.fragrance.id)}
        seen.add(str(selected.fragrance.id))
        remaining = sum(str(identifier) not in seen for identifier in candidates)
        return response.model_copy(
            update={
                **{
                    key: value
                    for key, value in selected.__dict__.items()
                    if key
                    in {
                        "fragrance",
                        "score",
                        "evidence_coverage",
                        "recommended_sprays",
                        "score_components",
                        "reasons",
                        "warnings",
                    }
                },
                "alternatives": [
                    candidate
                    for identifier, candidate in candidates.items()
                    if identifier != selected.fragrance.id
                ],
                "remaining_options": remaining,
                "options_exhausted": remaining == 0,
            }
        )

    def next(
        self, user_id: UUID, recommendation_id: UUID, request: RecommendationNextRequest
    ) -> WearRecommendationResponse:
        from scentiq_api.services.wear_recommendations import WearRecommendationService

        engine = WearRecommendationService(self.session)
        record = engine.get(user_id, recommendation_id, lock=True)
        receipt = self.session.scalar(
            select(RecommendationChoiceReceipt).where(
                RecommendationChoiceReceipt.recommendation_id == recommendation_id,
                RecommendationChoiceReceipt.idempotency_key == request.idempotency_key,
            )
        )
        if receipt:
            if (
                receipt.reset != request.reset
                or receipt.expected_fragrance_id != request.expected_fragrance_id
            ):
                raise conflict("idempotency_conflict", "Use a new key for a different request")
            saved = WearRecommendationResponse.model_validate(receipt.response_data)
            from scentiq_api.services.taste_profile import TasteProfileService

            owned = set(
                self.session.scalars(
                    select(UserCollectionItem.fragrance_id).where(
                        UserCollectionItem.user_id == user_id, UserCollectionItem.status == "owned"
                    )
                )
            )
            owned -= TasteProfileService(self.session).for_user(user_id).excluded_ids
            if saved.fragrance.id not in owned:
                raise conflict(
                    "recommendation_changed",
                    "Your collection or preferences changed; refresh recommendations",
                )
            return saved.model_copy(
                update={
                    "alternatives": [
                        candidate
                        for candidate in saved.alternatives
                        if candidate.fragrance.id in owned
                    ]
                }
            )
        response = self.current(user_id, engine._response(user_id, record))
        state = self.session.get(RecommendationChoice, recommendation_id)
        if state is None:
            state = RecommendationChoice(
                recommendation_id=recommendation_id,
                selected_fragrance_id=response.fragrance.id,
                seen_ids=[str(response.fragrance.id)],
            )
            self.session.add(state)
        else:
            # A member can explicitly accept a different alternative after browsing.
            # It is displayed and therefore consumed before the next advance.
            state.selected_fragrance_id = response.fragrance.id
            state.seen_ids = list(dict.fromkeys([*state.seen_ids, str(response.fragrance.id)]))
        if (
            request.expected_fragrance_id is not None
            and request.expected_fragrance_id != response.fragrance.id
            and not request.reset
        ):
            self.session.add(
                RecommendationChoiceReceipt(
                    recommendation_id=recommendation_id,
                    idempotency_key=request.idempotency_key,
                    reset=request.reset,
                    expected_fragrance_id=request.expected_fragrance_id,
                    response_data=response.model_dump(mode="json"),
                )
            )
            self.session.flush()
            return response
        # Advancing unlocks an accepted choice without treating it as a dislike.
        from scentiq_api.models import RecommendationDecision

        decision = self.session.scalar(
            select(RecommendationDecision).where(
                RecommendationDecision.recommendation_id == recommendation_id,
                RecommendationDecision.user_id == user_id,
            )
        )
        if decision:
            self.session.delete(decision)
            response = response.model_copy(update={"decision": None})
        candidates = [response, *response.alternatives]
        if request.reset:
            candidates.sort(
                key=lambda candidate: (
                    candidate.fragrance.id != record.fragrance_id,
                    -candidate.score,
                    str(candidate.fragrance.id),
                )
            )
            state.seen_ids = []
        unseen = next(
            (
                candidate
                for candidate in candidates
                if str(candidate.fragrance.id) not in state.seen_ids
            ),
            None,
        )
        if unseen:
            state.selected_fragrance_id = unseen.fragrance.id
            state.seen_ids = [*state.seen_ids, str(unseen.fragrance.id)]
        self.session.flush()
        result = self.current(user_id, response)
        self.session.add(
            RecommendationChoiceReceipt(
                recommendation_id=recommendation_id,
                idempotency_key=request.idempotency_key,
                reset=request.reset,
                expected_fragrance_id=request.expected_fragrance_id,
                response_data=result.model_dump(mode="json"),
            )
        )
        self.session.flush()
        return result

    def feedback(
        self, user_id: UUID, recommendation_id: UUID, request: RecommendationFeedbackRequest
    ) -> RecommendationFeedbackResponse:
        from scentiq_api.services.wear_recommendations import WearRecommendationService

        engine = WearRecommendationService(self.session)
        record = engine.get(user_id, recommendation_id, lock=True)
        response = self.current(user_id, engine._response(user_id, record))
        if request.fragrance_id not in {
            candidate.fragrance.id for candidate in [response, *response.alternatives]
        }:
            raise not_found("Eligible fragrance not found")
        entry = RecommendationFeedback(
            user_id=user_id,
            recommendation_id=recommendation_id,
            fragrance_id=request.fragrance_id,
            reason=request.reason,
        )
        self.session.add(entry)
        self.session.flush()
        return RecommendationFeedbackResponse(id=entry.id, reason=request.reason)
