"""Enumerated contract values.

Every value is lower-case and matches the database check constraints exactly, so
a payload that validates here cannot be rejected by PostgreSQL.
"""

from typing import Literal

Season = Literal["spring", "summer", "fall", "winter"]
Projection = Literal["intimate", "moderate", "strong"]
Occasion = Literal[
    "work",
    "casual",
    "date",
    "dinner",
    "party",
    "formal",
    "gym",
    "travel",
    "other",
]
OwnershipType = Literal["bottle", "decant", "sample"]
CollectionStatus = Literal["owned", "wishlist", "finished", "sold"]
NoteStage = Literal["top", "middle", "base", "general"]
LifecycleState = Literal["active", "deletion_pending"]

# Statuses that retain history instead of being hard-deleted.
RETIRED_STATUSES: tuple[str, ...] = ("finished", "sold")
