from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from scentiq_api.models.base import Base


class AIUsageMonth(Base):
    """Global inference ledger, in integer millionths of a US dollar."""

    __tablename__ = "ai_usage_months"
    month: Mapped[str] = mapped_column(String(7), primary_key=True)
    charged_microusd: Mapped[int] = mapped_column(Integer, default=0)


class AIRankingCache(Base):
    __tablename__ = "ai_ranking_cache"
    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AIUsageReservation(Base):
    __tablename__ = "ai_usage_reservations"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    month: Mapped[str] = mapped_column(ForeignKey("ai_usage_months.month"), index=True)
    amount_microusd: Mapped[int] = mapped_column(Integer)
    actual_microusd: Mapped[int | None] = mapped_column(Integer, nullable=True)
