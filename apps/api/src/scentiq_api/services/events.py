"""Record implicit interaction events; taste folds them in when it is next derived."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from scentiq_api.models.learning import InteractionEvent
from scentiq_api.repositories.layering import LayeringRepository
from scentiq_api.schemas.events import InteractionEventBatch, InteractionEventResult


class EventService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._layering = LayeringRepository(session)

    def record(self, user_id: UUID, batch: InteractionEventBatch) -> InteractionEventResult:
        stored = 0
        for event in batch.events:
            # Only fragrances in the member's own collection are kept.
            owned = (
                {item.id for item in self._layering.owned_pair(user_id, set(event.fragrance_ids))}
                if event.fragrance_ids
                else set()
            )
            self._session.add(
                InteractionEvent(
                    user_id=user_id,
                    event_type=event.event_type,
                    subject_type=event.subject_type,
                    fragrance_ids=[str(item) for item in event.fragrance_ids if item in owned],
                    context=event.context,
                )
            )
            stored += 1
        self._session.flush()
        return InteractionEventResult(recorded=stored)
