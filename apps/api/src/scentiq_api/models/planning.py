from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from scentiq_api.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin


class CalendarEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "calendar_events"
    __table_args__ = (
        UniqueConstraint("user_id", "external_reference", name="calendar_user_external_reference"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    external_reference: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(200))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    event_type: Mapped[str] = mapped_column(String(20))
    setting: Mapped[str | None] = mapped_column(String(40))
    formality: Mapped[str | None] = mapped_column(String(20))
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)


class WeatherSnapshot(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "weather_snapshots"
    __table_args__ = (
        CheckConstraint("humidity IS NULL OR humidity BETWEEN 0 AND 100", name="humidity_range"),
        CheckConstraint(
            "precipitation_probability IS NULL OR precipitation_probability BETWEEN 0 AND 1",
            name="precipitation_probability_range",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    location_label: Mapped[str] = mapped_column(String(160))
    forecast_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    temperature_celsius: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    humidity: Mapped[int | None]
    precipitation_probability: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    condition: Mapped[str] = mapped_column(String(40))
    source: Mapped[str] = mapped_column(String(80))


class Recommendation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 100", name="score_range"),
        CheckConstraint("recommended_sprays BETWEEN 1 AND 30", name="recommended_sprays_range"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    recommended_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    context: Mapped[str] = mapped_column(String(40))
    fragrance_id: Mapped[UUID] = mapped_column(ForeignKey("fragrances.id"))
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    recommended_sprays: Mapped[int]
    reasons: Mapped[list[str]] = mapped_column(JSON)
    warnings: Mapped[list[str]] = mapped_column(JSON)
    algorithm_version: Mapped[str] = mapped_column(String(40))


class RecommendationCandidate(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "recommendation_candidates"
    __table_args__ = (
        CheckConstraint("rank > 0", name="rank_positive"),
        CheckConstraint("score BETWEEN 0 AND 100", name="score_range"),
        UniqueConstraint(
            "recommendation_id", "fragrance_id", name="recommendation_candidate_fragrance"
        ),
        UniqueConstraint("recommendation_id", "rank", name="recommendation_candidate_rank"),
    )

    recommendation_id: Mapped[UUID] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"), index=True
    )
    fragrance_id: Mapped[UUID] = mapped_column(ForeignKey("fragrances.id"))
    rank: Mapped[int]
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    score_components: Mapped[dict[str, float]] = mapped_column(JSON)


class LayeringLog(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "layering_logs"
    __table_args__ = (
        CheckConstraint(
            "primary_fragrance_id <> secondary_fragrance_id", name="distinct_fragrances"
        ),
        CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="rating_range"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    primary_fragrance_id: Mapped[UUID] = mapped_column(ForeignKey("fragrances.id"))
    secondary_fragrance_id: Mapped[UUID] = mapped_column(ForeignKey("fragrances.id"))
    worn_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    rating: Mapped[int | None]
    notes: Mapped[str | None]
