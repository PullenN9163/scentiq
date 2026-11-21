"""Implicit interaction events that refine the derived taste profile."""

from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from scentiq_api.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class InteractionEvent(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One user action inside Scent IQ. Contains ids and filter keys, never free text."""

    __tablename__ = "interaction_events"
    __table_args__ = (Index("ix_interaction_events_user_created", "user_id", "created_at"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(30))
    subject_type: Mapped[str] = mapped_column(String(20))
    fragrance_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    context: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
