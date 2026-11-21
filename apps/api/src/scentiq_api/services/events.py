"""Record interaction events and feed the learned taste profile."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from scentiq_api.models.learning import InteractionEvent
from scentiq_api.repositories.layering import LayeringRepository
from scentiq_api.schemas.events import InteractionEventBatch, InteractionEventResult
from scentiq_api.services.layer_stack_scoring import signals
from scentiq_api.services.taste_profile import TasteProfileService, polarity


class EventService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._layering = LayeringRepository(session)
        self._taste = TasteProfileService(session)

    def record(self, user_id: UUID, batch: InteractionEventBatch) -> InteractionEventResult:
        learned = 0
        for event in batch.events:
            self._session.add(
                InteractionEvent(
                    user_id=user_id,
                    event_type=event.event_type,
                    subject_type=event.subject_type,
                    fragrance_ids=[str(item) for item in event.fragrance_ids],
                    context=event.context,
                )
            )
            strength = polarity(event.event_type, event.rating)
            if not event.fragrance_ids or strength == 0:
                continue
            # Only fragrances in the user's own collection may shape their profile.
            owned = self._layering.owned_pair(user_id, set(event.fragrance_ids))
            if not owned:
                continue
            self._taste.learn(user_id, [signals(item) for item in owned], strength)
            learned += 1
        self._session.flush()
        return InteractionEventResult(recorded=len(batch.events), learned=learned)
