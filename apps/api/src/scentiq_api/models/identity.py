from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from scentiq_api.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from scentiq_api.models.users import User

IDENTITY_PROVIDERS = ("clerk",)


class UserIdentity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Maps an external identity provider subject to an internal ScentIQ user."""

    __tablename__ = "user_identities"
    __table_args__ = (
        UniqueConstraint("provider", "subject", name="identity_provider_subject"),
        CheckConstraint("provider IN ('clerk')", name="provider_value"),
    )

    provider: Mapped[str] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(String(255))
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, unique=True
    )

    user: Mapped[User] = relationship(back_populates="identity")


class IdentityEvent(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Ledger of processed provider identity events, keyed for idempotent replay."""

    __tablename__ = "identity_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="identity_event_provider_event"),
        CheckConstraint("provider IN ('clerk')", name="provider_value"),
        CheckConstraint(
            "event_type IN ('user.deleted')",
            name="event_type_value",
        ),
    )

    provider: Mapped[str] = mapped_column(String(20))
    event_id: Mapped[str] = mapped_column(String(255))
    event_type: Mapped[str] = mapped_column(String(40))
    subject: Mapped[str] = mapped_column(String(255), index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
