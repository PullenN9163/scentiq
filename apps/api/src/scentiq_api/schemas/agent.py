"""Bounded, ephemeral advisor requests and public NDJSON events."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AgentTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class AgentChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=2000)
    history: list[AgentTurn] = Field(default_factory=list, max_length=8)

    @field_validator("message")
    @classmethod
    def nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Enter a question")
        return value

    @model_validator(mode="after")
    def bounded_history(self) -> AgentChatRequest:
        if len(self.message) + sum(len(turn.content) for turn in self.history) > 12000:
            raise ValueError("Conversation is too long")
        return self


class AgentCard(BaseModel):
    kind: Literal[
        "recommendation",
        "week",
        "collection",
        "insights",
        "wears",
        "discover",
        "layering",
        "fragrance",
    ]
    data: Any


class AgentStreamEvent(BaseModel):
    type: Literal[
        "status", "tool_started", "tool_finished", "text_delta", "card", "fallback", "done"
    ]
    label: str | None = None
    tool: str | None = None
    delta: str | None = None
    card: AgentCard | None = None
