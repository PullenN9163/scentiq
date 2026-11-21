from datetime import UTC, datetime

from layering_helpers import scents
from sqlalchemy import select
from sqlalchemy.orm import Session

from scentiq_api.models import InteractionEvent
from scentiq_api.schemas.wear_recommendations import (
    RecommendationDecisionRequest,
    RecommendationWearRequest,
)
from scentiq_api.services.taste_profile import TasteProfileService
from scentiq_api.services.wear_recommendations import WearRecommendationService

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


def test_week_rotates_picks_across_days(session: Session) -> None:
    user, _ = scents(session)
    plan = WearRecommendationService(session, clock=lambda: NOW).week(user.id)
    days = [r for r in plan.recommendations if r.context.source == "day"]
    assert len(days) == 7
    assert len({r.fragrance.id for r in days}) > 1


def test_rotation_can_include_blend_candidates_with_zones_and_percent(session: Session) -> None:
    user, _ = scents(session)
    plan = WearRecommendationService(session, clock=lambda: NOW).week(user.id)
    blends = [
        candidate
        for rec in plan.recommendations
        for candidate in (rec, *rec.alternatives)
        if candidate.blend is not None
    ]
    assert blends, "expected at least one blend among the week's candidates"
    blend = blends[0]
    assert blend.blend_key and 0 <= blend.blend.score_percent <= 100
    assert all(item.zones for item in blend.blend.items)


def test_choosing_an_alternative_teaches_taste_and_logs_events(session: Session) -> None:
    user, _ = scents(session)
    service = WearRecommendationService(session, clock=lambda: NOW)
    top = service.today(user.id).recommendations[0]
    chosen = next(c for c in top.alternatives if c.fragrance.name == "Anchor" and not c.blend_key)
    service.decide(
        user.id,
        top.id,
        RecommendationDecisionRequest(action="replaced", selected_fragrance_id=chosen.fragrance.id),
    )
    assert TasteProfileService(session).affinities(user.id).get("woody", 0) > 0
    events = session.scalars(
        select(InteractionEvent).where(InteractionEvent.user_id == user.id)
    ).all()
    assert {e.event_type for e in events} == {"accept", "reject"}


def test_wearing_a_blend_logs_every_member(session: Session) -> None:
    from scentiq_api.models import WearLog

    user, _ = scents(session)
    service = WearRecommendationService(session, clock=lambda: NOW)
    rec, blend = next(
        (rec, c)
        for rec in service.week(user.id).recommendations
        for c in (rec, *rec.alternatives)
        if c.blend is not None
    )
    service.wear(
        user.id,
        rec.id,
        RecommendationWearRequest(
            selected_fragrance_id=blend.fragrance.id, blend_key=blend.blend_key
        ),
    )
    logged = session.scalars(select(WearLog).where(WearLog.user_id == user.id)).all()
    assert len(logged) == len(blend.blend.items)
