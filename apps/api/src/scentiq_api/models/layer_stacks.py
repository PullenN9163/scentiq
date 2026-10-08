"""Normalized, member-owned layering combinations and wear history."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from scentiq_api.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin


class LayerStack(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "layer_stacks"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    mode: Mapped[str] = mapped_column(String(20))
    goal: Mapped[str | None] = mapped_column(String(30))
    notes: Mapped[str | None] = mapped_column(Text)
    score_snapshot: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0"))
    evidence_coverage: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0"))
    algorithm_version: Mapped[str] = mapped_column(String(40), default="layering-v2")
    score_components: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    items: Mapped[list[LayerStackItem]] = relationship(
        cascade="all, delete-orphan", order_by="LayerStackItem.position"
    )
    wears: Mapped[list[LayerStackWear]] = relationship(cascade="all, delete-orphan")


class LayerStackItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "layer_stack_items"
    __table_args__ = (
        UniqueConstraint("stack_id", "fragrance_id", name="layer_stack_fragrance"),
        UniqueConstraint("stack_id", "position", name="layer_stack_position"),
        CheckConstraint("position BETWEEN 1 AND 3", name="position_range"),
        CheckConstraint("suggested_sprays BETWEEN 1 AND 6", name="sprays_range"),
        CheckConstraint("role IN ('anchor', 'bridge', 'accent')", name="role_value"),
    )
    stack_id: Mapped[UUID] = mapped_column(
        ForeignKey("layer_stacks.id", ondelete="CASCADE"), index=True
    )
    fragrance_id: Mapped[UUID] = mapped_column(ForeignKey("fragrances.id", ondelete="CASCADE"))
    position: Mapped[int]
    role: Mapped[str] = mapped_column(String(10))
    suggested_sprays: Mapped[int]


class LayerStackWear(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "layer_stack_wears"
    __table_args__ = (
        CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="rating_range"),
    )
    stack_id: Mapped[UUID] = mapped_column(
        ForeignKey("layer_stacks.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    worn_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    rating: Mapped[int | None]
    notes: Mapped[str | None] = mapped_column(Text)
