from datetime import UTC, datetime

from layering_helpers import scents
from sqlalchemy.orm import Session

from scentiq_api.schemas.events import InteractionEventBatch, InteractionEventIn
from scentiq_api.schemas.wear_recommendations import RecommendationDecisionRequest
from scentiq_api.services.events import EventService
from scentiq_api.services.taste_profile import TasteProfileService
from scentiq_api.services.wear_recommendations import WearRecommendationService

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


def test_saving_a_blend_teaches_the_members_notes_and_accords(session: Session) -> None:
    user, items = scents(session)
    before = TasteProfileService(session).for_user(user.id).features.get("accord:citrus", 0)
    EventService(session).record(
        user.id,
        InteractionEventBatch(
            events=[
                InteractionEventIn(
                    event_type="stack_save",
                    subject_type="stack",
                    fragrance_ids=[items[0].id, items[1].id],
                )
            ]
        ),
    )
    after = TasteProfileService(session).for_user(user.id).features.get("accord:citrus", 0)
    assert after > before


def test_discarding_a_blend_pushes_taste_the_other_way(session: Session) -> None:
    user, items = scents(session)
    EventService(session).record(
        user.id,
        InteractionEventBatch(
            events=[
                InteractionEventIn(
                    event_type="stack_discard", subject_type="stack", fragrance_ids=[items[2].id]
                )
            ]
        ),
    )
    assert TasteProfileService(session).for_user(user.id).features["accord:amber"] < 0


def test_events_only_keep_owned_fragrances_and_changing_taste_changes_its_version(
    session: Session,
) -> None:
    from uuid import uuid4

    from sqlalchemy import select

    from scentiq_api.models import InteractionEvent

    user, items = scents(session)
    service = TasteProfileService(session)
    first = service.for_user(user.id).version
    EventService(session).record(
        user.id,
        InteractionEventBatch(
            events=[
                InteractionEventIn(event_type="stack_wear", fragrance_ids=[items[0].id, uuid4()])
            ]
        ),
    )
    stored = session.scalars(select(InteractionEvent)).one()
    assert stored.fragrance_ids == [str(items[0].id)]
    assert service.for_user(user.id).version != first


def test_choosing_an_alternative_teaches_taste(session: Session) -> None:
    user, _ = scents(session)
    service = WearRecommendationService(session, clock=lambda: NOW)
    top = service.today(user.id).recommendations[0]
    chosen = next(c for c in top.alternatives if c.fragrance.name == "Anchor")
    service.decide(
        user.id,
        top.id,
        RecommendationDecisionRequest(action="replaced", selected_fragrance_id=chosen.fragrance.id),
    )
    assert TasteProfileService(session).for_user(user.id).features.get("accord:woody", 0) > 0
