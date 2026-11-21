"""Member-specific displayed choices and retry receipts for persisted wear batches."""

from uuid import UUID

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from scentiq_api.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class RecommendationChoice(Base):
    __tablename__ = "recommendation_choices"
    recommendation_id: Mapped[UUID] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"), primary_key=True
    )
    selected_fragrance_id: Mapped[UUID] = mapped_column(
        ForeignKey("fragrances.id", ondelete="CASCADE")
    )
    seen_ids: Mapped[list[str]] = mapped_column(JSON, default=list)


class RecommendationChoiceReceipt(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "recommendation_choice_receipts"
    __table_args__ = (UniqueConstraint("recommendation_id", "idempotency_key"),)
    recommendation_id: Mapped[UUID] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE")
    )
    idempotency_key: Mapped[UUID]
    expected_fragrance_id: Mapped[UUID | None]
    reset: Mapped[bool]
    response_data: Mapped[dict[str, object]] = mapped_column(JSON)


class RecommendationFeedback(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "recommendation_feedback"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    recommendation_id: Mapped[UUID] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE")
    )
    fragrance_id: Mapped[UUID] = mapped_column(ForeignKey("fragrances.id", ondelete="CASCADE"))
    reason: Mapped[str] = mapped_column(String(24))
