"""Interaction events and the per-user taste profile learned from them."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, func
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


class UserTasteProfile(Base):
    __tablename__ = "user_taste_profiles"
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # note/accord/family slug -> learned affinity in [-1, 1]
    affinities: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    # recommendation component name -> learned multiplier around 1.0
    component_weights: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
