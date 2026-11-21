"""Member-owned derived taste cache; raw private feedback is never copied here."""

from uuid import UUID

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from scentiq_api.models.base import Base, TimestampMixin


class UserTasteProfile(TimestampMixin, Base):
    __tablename__ = "user_taste_profiles"
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    version: Mapped[str] = mapped_column(String(64))
    features: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
