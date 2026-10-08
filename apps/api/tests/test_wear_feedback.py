from datetime import UTC, datetime

import pytest
from domain_fixtures import make_brand, make_collection_item, make_fragrance, make_user
from sqlalchemy.orm import Session

from scentiq_api.errors import ApiError
from scentiq_api.schemas.wear import WearFeedbackRequest
from scentiq_api.schemas.wear_recommendations import (
    RecommendationDecisionRequest,
    RecommendationWearRequest,
)
from scentiq_api.services.wear_feedback import WearFeedbackService
from scentiq_api.services.wear_recommendations import WearRecommendationService


def test_conversion_decisions_feedback_and_isolation(session: Session) -> None:
    user = make_user(session, email="conversion@example.test")
    other = make_user(session, email="foreignconversion@example.test")
    brand = make_brand(session, name="ConversionBrand")
    for name in ("Amber", "Citrus"):
        make_collection_item(
            session, user=user, fragrance=make_fragrance(session, brand=brand, name=name)
        )
    service = WearRecommendationService(
        session, clock=lambda: datetime(2026, 10, 7, 12, tzinfo=UTC)
    )
    recommendation = service.today(user.id).recommendations[0]
    selected = recommendation.alternatives[0].fragrance.id
    service.decide(
        user.id,
        recommendation.id,
        RecommendationDecisionRequest(action="replaced", selected_fragrance_id=selected),
    )
    entry = service.wear(
        user.id, recommendation.id, RecommendationWearRequest(selected_fragrance_id=selected)
    )
    assert entry.recommendation_id == recommendation.id
    assert entry.fragrance_id == selected
    feedback = WearFeedbackService(session)
    assert feedback.get(user.id, entry.id) is None
    saved = feedback.put(
        user.id, entry.id, WearFeedbackRequest(rating=5, longevity=8, projection="moderate")
    )
    assert saved.rating == 5
    updated = feedback.put(user.id, entry.id, WearFeedbackRequest(rating=4))
    assert updated.id == saved.id
    with pytest.raises(ApiError):
        feedback.get(other.id, entry.id)
    with pytest.raises(ApiError):
        service.wear(other.id, recommendation.id, RecommendationWearRequest())
    with pytest.raises(ApiError):
        service.decide(
            user.id,
            recommendation.id,
            RecommendationDecisionRequest(action="replaced", selected_fragrance_id=other.id),
        )


def test_accepting_retired_recommendation_is_refused(session: Session) -> None:
    user = make_user(session, email="retired-recommendation@example.test")
    fragrance = make_fragrance(
        session, brand=make_brand(session, name="RetiredBrand"), name="Retired"
    )
    item = make_collection_item(session, user=user, fragrance=fragrance)
    service = WearRecommendationService(
        session, clock=lambda: datetime(2026, 10, 7, 12, tzinfo=UTC)
    )
    recommendation = service.today(user.id).recommendations[0]
    item.status = "sold"
    session.flush()
    with pytest.raises(ApiError):
        service.decide(user.id, recommendation.id, RecommendationDecisionRequest(action="accepted"))
