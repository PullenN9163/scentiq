"""Deterministic occasion and formality for a calendar event.

Planning needs to know whether a day holds a client meeting, a workout or a
wedding. This reads only the title, which is all ScentIQ keeps, and prefers the
more specific occasion when several match: "team dinner" is a dinner, and
"wedding drinks" is formal.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from scentiq_api.models import UserPreference
from scentiq_api.schemas.enums import Occasion
from scentiq_api.services.ai_ranking import rank_candidates

Formality = str  # "formal" | "smart" | "casual"

# Checked in order; the first occasion with a matching keyword wins.
_KEYWORDS: tuple[tuple[Occasion, tuple[str, ...]], ...] = (
    (
        "formal",
        (
            "wedding",
            "gala",
            "ceremony",
            "funeral",
            "black tie",
            "opera",
            "ballet",
            "awards",
            "graduation",
            "christening",
        ),
    ),
    ("travel", ("flight", "airport", "travel", "trip", "layover", "boarding")),
    (
        "gym",
        (
            "gym",
            "workout",
            "yoga",
            "pilates",
            "running",
            "spin",
            "crossfit",
            "hiit",
            "swim",
            "tennis",
            "climbing",
            "training session",
            "bootcamp",
        ),
    ),
    ("date", ("date", "date night", "anniversary", "valentine", "valentines")),
    (
        "party",
        (
            "party",
            "birthday",
            "drinks",
            "happy hour",
            "celebration",
            "concert",
            "festival",
            "club",
            "housewarming",
        ),
    ),
    ("dinner", ("dinner", "supper", "restaurant", "tasting menu")),
    (
        "work",
        (
            "meeting",
            "standup",
            "stand-up",
            "stand up",
            "sync",
            "1:1",
            "1-1",
            "one-on-one",
            "interview",
            "review",
            "call",
            "client",
            "presentation",
            "workshop",
            "conference",
            "office",
            "sprint",
            "retro",
            "demo",
            "planning",
            "offsite",
            "board",
            "pitch",
            "onboarding",
        ),
    ),
    (
        "casual",
        (
            "lunch",
            "brunch",
            "coffee",
            "walk",
            "shopping",
            "errands",
            "picnic",
            "park",
            "movie",
            "cinema",
            "museum",
            "hangout",
        ),
    ),
)

_FORMALITY: dict[Occasion, Formality | None] = {
    "formal": "formal",
    "date": "smart",
    "dinner": "smart",
    "party": "smart",
    "work": "smart",
    "travel": "casual",
    "gym": "casual",
    "casual": "casual",
    "other": None,
}

_PATTERNS = tuple(
    (
        occasion,
        re.compile(
            r"(?<![\w])(?:" + "|".join(re.escape(keyword) for keyword in keywords) + r")(?![\w])"
        ),
    )
    for occasion, keywords in _KEYWORDS
)


@dataclass(frozen=True)
class EventClassification:
    occasion: Occasion
    formality: Formality | None
    source: str = "keyword"


def classify_event(title: str) -> EventClassification:
    folded = title.casefold()
    for occasion, pattern in _PATTERNS:
        if pattern.search(folded):
            return EventClassification(occasion, _FORMALITY[occasion])
    return EventClassification("other", None)


def interpret_event_title(
    session: Session, user_id: UUID, title: str, starts_at: datetime
) -> EventClassification:
    """Interpret ambiguous titles only after explicit member consent.

    The shared ranker enforces deployment flags, budget, deadline and enum membership.
    No provider-generated text or event title enters stored explanations or logs.
    """
    baseline = classify_event(title)
    preferences = session.get(UserPreference, user_id)
    if (
        baseline.occasion != "other"
        or not preferences
        or not preferences.calendar_ai_titles_enabled
    ):
        return baseline
    candidates = [
        {
            "candidate_id": occasion,
            "baseline_score": 100 if occasion == "other" else 0,
            "evidence": {"occasion": occasion},
        }
        for occasion in _FORMALITY
    ]
    result = rank_candidates(
        session,
        user_id,
        candidates=candidates,
        context={
            "calendar_title": title[:200],
            "task": "Classify the calendar event occasion; choose other if unclear.",
        },
        fingerprint=hashlib.sha256((title[:200] + starts_at.isoformat()).encode()).hexdigest(),
        surface="today",
    )
    if result.generation_mode == "ai" and result.ordered_ids:
        winner = result.ordered_ids[0]
        for occasion, formality in _FORMALITY.items():
            if winner == occasion:
                return EventClassification(occasion, formality, "ai")
    return baseline
