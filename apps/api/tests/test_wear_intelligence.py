from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from domain_fixtures import make_brand, make_collection_item, make_fragrance, make_user
from sqlalchemy.orm import Session

from scentiq_api.errors import ApiError
from scentiq_api.schemas.wear_recommendations import (
    RecommendationContext,
    RecommendationPreviewRequest,
)
from scentiq_api.services.wear_recommendations import WearRecommendationService
from scentiq_api.services.wear_scoring import CandidateInput, score_candidate

NOW = datetime(2026, 10, 7, 12, tzinfo=UTC)


def context(**changes: object) -> RecommendationContext:
    return RecommendationContext.model_validate(
        {
            "context_key": "day:2026-10-07",
            "recommended_for": NOW,
            "local_date": "2026-10-07",
            "timezone": "UTC",
            "season": "fall",
            "daypart": "day",
            "source": "today",
            **changes,
        }
    )


@pytest.mark.parametrize(
    "occasion,setting,temperature,projection",
    [
        ("work", "indoor", 34, "strong"),
        ("date", "outdoor", -4, "intimate"),
        ("gym", None, None, None),
        ("casual", "outdoor", 30, "moderate"),
        ("formal", "indoor", 12, "strong"),
        (None, None, None, None),
    ],
)
def test_scores_bounded_honest_and_sprays_capped(
    occasion: str | None,
    setting: str | None,
    temperature: float | None,
    projection: str | None,
) -> None:
    result = score_candidate(
        CandidateInput(fragrance_id=uuid4(), projection=projection),
        context(occasion=occasion, setting=setting, high_celsius=temperature),
        maximum_sprays=3,
    )
    assert 0 <= result.score <= 100
    assert result.components["occasion"] == 12.5
    assert 1 <= result.sprays <= 3
    assert result.evidence_coverage < 0.5


def test_extreme_weather_and_rotation_rejection_do_not_overpower_context() -> None:
    candidate = CandidateInput(
        fragrance_id=uuid4(),
        projection="strong",
        longevity=10,
        season_weights={"fall": 1},
        occasion_weights={"work": 1},
        rating=5,
    )
    baseline = score_candidate(
        candidate, context(occasion="work", setting="indoor", high_celsius=35)
    )
    penalized = score_candidate(
        candidate.model_copy(update={"days_since_wear": 0, "rejections": 3}),
        context(occasion="work", setting="indoor", high_celsius=35),
    )
    assert penalized.score < baseline.score
    assert penalized.components["penalties"] >= -30
    assert baseline.sprays == 1
    assert baseline.warnings


def test_positive_same_context_feedback_is_bounded() -> None:
    candidate = CandidateInput(fragrance_id=uuid4())
    baseline = score_candidate(candidate, context())
    positive = score_candidate(candidate.model_copy(update={"feedback_rating": 5}), context())
    assert 0 < positive.score - baseline.score <= 3


def test_missing_data_is_neutral_and_evidence_not_confidence() -> None:
    result = score_candidate(CandidateInput(fragrance_id=uuid4()), context())
    assert result.components["weather"] == 10
    assert result.components["season"] == 7.5
    assert result.components["time_of_day"] == 5
    assert result.evidence_coverage == pytest.approx(1 / 7)


def test_persisted_plan_is_idempotent_empty_and_isolated(session: Session) -> None:
    user = make_user(session, email="wear@example.test")
    other = make_user(session, email="otherwear@example.test")
    service = WearRecommendationService(session, clock=lambda: NOW)
    assert service.today(user.id).recommendations == []
    fragrance = make_fragrance(
        session, brand=make_brand(session, name="WearBrand"), name="WearFragrance"
    )
    make_collection_item(session, user=user, fragrance=fragrance)
    first = service.today(user.id).recommendations[0]
    assert first.id == service.today(user.id).recommendations[0].id
    assert len(service.week(user.id).recommendations) == 7
    assert service.today(other.id).recommendations == []
    with pytest.raises(ApiError):
        service.get(other.id, first.id)


def test_timezone_preview_and_deterministic_tie_break(session: Session) -> None:
    user = make_user(session, email="tie@example.test")
    brand = make_brand(session, name="TieBrand")
    for name in ("Beta", "Alpha"):
        make_collection_item(
            session, user=user, fragrance=make_fragrance(session, brand=brand, name=name)
        )
    service = WearRecommendationService(session, clock=lambda: NOW)
    request = RecommendationPreviewRequest(
        occasion="dinner", recommended_for=NOW + timedelta(hours=7)
    )
    result = service.preview(user.id, request)
    assert result.fragrance.name == "Alpha"
    assert result.context.occasion == "dinner"
    assert result.id == service.preview(user.id, request).id


def test_logged_wear_changes_same_day_rotation_and_preserves_history(session: Session) -> None:
    from scentiq_api.schemas.wear_recommendations import RecommendationWearRequest

    user = make_user(session, email="rotationtoday@example.test")
    fragrance = make_fragrance(
        session, brand=make_brand(session, name="TodayRotation"), name="TodayWear"
    )
    make_collection_item(session, user=user, fragrance=fragrance)
    service = WearRecommendationService(session, clock=lambda: NOW)
    before = service.today(user.id).recommendations[0]
    service.wear(user.id, before.id, RecommendationWearRequest())
    after = service.today(user.id).recommendations[0]
    assert after.id != before.id
    assert after.score_components["rotation"] < before.score_components["rotation"]
    assert service.get(user.id, before.id).id == before.id
    assert after.id == service.today(user.id).recommendations[0].id


def test_visible_materially_different_events_and_user_overrides(session: Session) -> None:
    from decimal import Decimal

    from scentiq_api.models import CalendarEvent, UserPreference

    user = make_user(session, email="eventcontexts@example.test")
    session.add(UserPreference(user_id=user.id, timezone="America/New_York", maximum_sprays=2))
    fragrance = make_fragrance(
        session, brand=make_brand(session, name="ContextBrand"), name="Contexts"
    )
    fragrance.projection_level = "strong"
    item = make_collection_item(session, user=user, fragrance=fragrance)
    item.custom_projection = "intimate"
    item.custom_longevity = Decimal("2")
    for hidden, hour, occasion in ((False, 14, "work"), (False, 23, "date"), (True, 15, "gym")):
        session.add(
            CalendarEvent(
                user_id=user.id,
                title="Private event",
                starts_at=NOW.replace(hour=hour),
                ends_at=NOW.replace(hour=hour) + timedelta(hours=1),
                event_type=occasion,
                is_hidden=hidden,
                setting="indoor",
            )
        )
    session.flush()
    service = WearRecommendationService(session, clock=lambda: NOW)
    plan = service.today(user.id)
    assert len(plan.recommendations) == 3
    assert {result.context.occasion for result in plan.recommendations} == {None, "work", "date"}
    assert all(result.recommended_sprays <= 2 for result in plan.recommendations)
    assert not any(
        "Strong projection" in warning
        for result in plan.recommendations
        for warning in result.warnings
    )
    assert service.week(user.id).recommendations[0].id == plan.recommendations[0].id


def test_poor_context_fit_does_not_claim_positive_matches() -> None:
    result = score_candidate(
        CandidateInput(
            fragrance_id=uuid4(), season_weights={"winter": 1}, occasion_weights={"party": 1}
        ),
        context(occasion="work"),
    )
    assert result.components["season"] == 0
    assert result.components["occasion"] == 0
    assert "Source-backed seasonal match" not in result.reasons
    assert "Fits recorded occasion evidence" not in result.reasons


def test_unsupported_performance_preferences_do_not_raise_evidence() -> None:
    result = score_candidate(
        CandidateInput(fragrance_id=uuid4()),
        context(),
        preferred_projection="strong",
        preferred_longevity=8,
    )
    assert result.evidence_coverage == pytest.approx(1 / 7)
