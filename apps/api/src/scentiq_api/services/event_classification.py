"""Deterministic occasion and formality for a calendar event.

Planning needs to know whether a day holds a client meeting, a workout or a
wedding. This reads only the title, which is all ScentIQ keeps, and prefers the
more specific occasion when several match: "team dinner" is a dinner, and
"wedding drinks" is formal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from scentiq_api.schemas.enums import Occasion

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


def classify_event(title: str) -> EventClassification:
    folded = title.casefold()
    for occasion, pattern in _PATTERNS:
        if pattern.search(folded):
            return EventClassification(occasion, _FORMALITY[occasion])
    return EventClassification("other", None)
