"""Persistent non-repeating discovery and layering batches."""

from uuid import UUID

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from scentiq_api.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class SurfaceChoiceBatch(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "surface_choice_batches"
    __table_args__ = (UniqueConstraint("user_id", "surface", "fingerprint"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    surface: Mapped[str] = mapped_column(String(16))
    fingerprint: Mapped[str] = mapped_column(String(64))
    candidates: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    selected_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    seen_keys: Mapped[list[str]] = mapped_column(JSON, default=list)


class SurfaceChoiceReceipt(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "surface_choice_receipts"
    __table_args__ = (UniqueConstraint("batch_id", "idempotency_key"),)
    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("surface_choice_batches.id", ondelete="CASCADE")
    )
    idempotency_key: Mapped[UUID]
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    response_data: Mapped[dict[str, object]] = mapped_column(JSON)
