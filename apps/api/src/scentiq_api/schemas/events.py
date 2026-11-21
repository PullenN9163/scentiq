from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

InteractionEventType = Literal[
    "view",
    "accept",
    "reject",
    "skip",
    "dismiss",
    "wear",
    "like",
    "dislike",
    "surprise_click",
    "surprise_shown",
    "filter_select",
    "stack_save",
    "stack_edit",
    "stack_discard",
    "stack_wear",
]


class InteractionEventIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_type: InteractionEventType
    subject_type: Literal["fragrance", "stack", "recommendation", "ui"] = "fragrance"
    fragrance_ids: list[UUID] = Field(default_factory=list, max_length=3)
    rating: int | None = Field(default=None, ge=1, le=5)
    # Short filter/context keys such as goal, mode, daypart. Never free text.
    context: dict[str, str] = Field(default_factory=dict, max_length=8)

    @field_validator("context")
    @classmethod
    def short_values(cls, value: dict[str, str]) -> dict[str, str]:
        if any(len(key) > 30 or len(item) > 40 for key, item in value.items()):
            raise ValueError("Context keys and values must be short identifiers")
        return value


class InteractionEventBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[InteractionEventIn] = Field(min_length=1, max_length=50)


class InteractionEventResult(BaseModel):
    recorded: int
