"""Online per-user taste learning. Pure functions plus a thin persistence service.

Two things are learned from interaction events:

* ``affinities``: signed preference for notes/accords/families, nudged by every positive
  (accept, wear, high rating, save) or negative (reject, skip, dismiss, discard) event and
  decayed so recent behaviour dominates.
* ``component_weights``: per recommendation-component multipliers fitted with a tiny online
  logistic step, so a user who always accepts weather-appropriate picks gets weather weighted up.

Both are clamped, explainable, and fall back to neutral for a new user.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from scentiq_api.models.learning import InteractionEvent, UserTasteProfile

DECAY = 0.97
LEARNING_RATE = 0.12
WEIGHT_RATE = 0.05
WEIGHT_BOUNDS = (0.5, 1.8)
MIN_EVENTS_FOR_WEIGHTS = 8

POSITIVE = {
    "accept": 1.0,
    "wear": 1.0,
    "stack_save": 0.8,
    "stack_wear": 1.0,
    "like": 1.0,
    "view_detail": 0.15,
}
NEGATIVE = {"reject": -1.0, "skip": -0.6, "dismiss": -0.5, "stack_discard": -0.7, "dislike": -1.0}


def polarity(event_type: str, rating: int | None = None) -> float:
    """Signed strength of an event, scaled by an explicit 1-5 rating when present."""
    if rating is not None:
        return (rating - 3) / 2
    return POSITIVE.get(event_type, NEGATIVE.get(event_type, 0.0))


def update_affinities(
    affinities: Mapping[str, float],
    signal_profiles: Iterable[Mapping[str, float]],
    strength: float,
) -> dict[str, float]:
    """Decay every affinity, then move the event's signals toward its polarity."""
    updated = {key: value * DECAY for key, value in affinities.items()}
    profiles = list(signal_profiles)
    for profile in profiles if strength else []:
        total = sum(profile.values()) or 1.0
        for key, weight in profile.items():
            share = weight / total
            current = updated.get(key, 0.0)
            updated[key] = max(-1.0, min(1.0, current + LEARNING_RATE * strength * share * 4))
    # Drop negligible entries so the stored JSON stays small.
    return {key: round(value, 4) for key, value in updated.items() if abs(value) >= 0.01}


def taste_affinity(affinities: Mapping[str, float], profile: Mapping[str, float]) -> float:
    """0-1 affinity of a scent's signal profile for this user; 0.5 means no information."""
    total = sum(profile.values())
    if not total or not affinities:
        return 0.5
    value = sum(weight * affinities.get(key, 0.0) for key, weight in profile.items()) / total
    return max(0.0, min(1.0, 0.5 + value * 0.5))


def update_component_weights(
    weights: Mapping[str, float],
    components: Mapping[str, float],
    accepted: bool,
) -> dict[str, float]:
    """One online logistic step. ``components`` are 0-1 normalised component scores."""
    keys = list(components)
    current = {key: weights.get(key, 1.0) for key in keys}
    logit = sum((current[key] - 1.0) * components[key] for key in keys)
    predicted = 1 / (1 + math.exp(-logit))
    error = (1.0 if accepted else 0.0) - predicted
    lower, upper = WEIGHT_BOUNDS
    merged = dict(weights)
    for key in keys:
        merged[key] = round(
            max(lower, min(upper, current[key] + WEIGHT_RATE * error * components[key])), 4
        )
    return merged


def exploration_bonus(shown: int, total_shown: int) -> float:
    """UCB-style bonus: under-shown items get a small boost, decaying with exposure."""
    if total_shown <= 0:
        return 0.0
    return min(0.08, 0.08 * math.sqrt(math.log(total_shown + 1) / (shown + 1)) / 2)


class TasteProfileService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def profile(self, user_id: UUID) -> UserTasteProfile:
        record = self._session.get(UserTasteProfile, user_id)
        if record is None:
            record = UserTasteProfile(
                user_id=user_id, affinities={}, component_weights={}, event_count=0
            )
            self._session.add(record)
            self._session.flush()
        return record

    def affinities(self, user_id: UUID) -> dict[str, float]:
        record = self._session.get(UserTasteProfile, user_id)
        return dict(record.affinities) if record else {}

    def component_weights(self, user_id: UUID) -> dict[str, float]:
        record = self._session.get(UserTasteProfile, user_id)
        if record is None or record.event_count < MIN_EVENTS_FOR_WEIGHTS:
            return {}
        return dict(record.component_weights)

    def learn(
        self,
        user_id: UUID,
        signal_profiles: Iterable[Mapping[str, float]],
        strength: float,
        *,
        components: Mapping[str, float] | None = None,
        accepted: bool | None = None,
    ) -> None:
        record = self.profile(user_id)
        record.affinities = update_affinities(record.affinities, signal_profiles, strength)
        if components is not None and accepted is not None:
            record.component_weights = update_component_weights(
                record.component_weights, components, accepted
            )
        record.event_count += 1
        self._session.flush()

    def recent_blend_keys(self, user_id: UUID, limit: int = 30) -> list[list[str]]:
        """Fragrance-id sets of the most recent surprise/suggestion views, to avoid repeats."""
        rows = self._session.scalars(
            select(InteractionEvent)
            .where(
                InteractionEvent.user_id == user_id,
                InteractionEvent.subject_type == "stack",
                InteractionEvent.event_type.in_(("surprise_shown", "view", "stack_discard")),
            )
            .order_by(InteractionEvent.created_at.desc())
            .limit(limit)
        )
        return [list(row.fragrance_ids) for row in rows]
