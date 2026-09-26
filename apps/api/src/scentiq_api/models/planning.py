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
    Text,
    UniqueConstraint,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column

from scentiq_api.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin


class CalendarConnection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One member's OAuth grant to one provider account."""

    __tablename__ = "calendar_connections"
    __table_args__ = (
        CheckConstraint("provider IN ('google', 'microsoft')", name="provider_value"),
        CheckConstraint("status IN ('active', 'reauth_required')", name="status_value"),
        UniqueConstraint(
            "user_id", "provider", "account_email", name="calendar_connection_account"
        ),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    account_email: Mapped[str] = mapped_column(String(320))
    # AES-GCM sealed; see integrations/crypto.py. Access tokens are never stored.
    encrypted_refresh_token: Mapped[str] = mapped_column(Text)
    scopes: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(40))


class CalendarSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A calendar inside a connected account, which the member can include or not."""

    __tablename__ = "calendar_sources"
    __table_args__ = (
        UniqueConstraint("connection_id", "provider_calendar_id", name="calendar_source_calendar"),
    )

    connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("calendar_connections.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider_calendar_id: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(String(200))
    color: Mapped[str | None] = mapped_column(String(20))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False)


class OAuthState(CreatedAtMixin, Base):
    """A pending authorization: single use, short lived, bound to one member."""

    __tablename__ = "oauth_states"

    # SHA-256 of the state value; the value itself only travels via the browser.
    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    code_verifier: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CalendarEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A synced event. Only what planning needs is kept: no descriptions,
    attendees or meeting links."""

    __tablename__ = "calendar_events"
    __table_args__ = (
        UniqueConstraint("user_id", "external_reference", name="calendar_user_external_reference"),
        UniqueConstraint("source_id", "provider_event_id", name="calendar_event_source_event"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    connection_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("calendar_connections.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("calendar_sources.id", ondelete="CASCADE"), index=True
    )
    provider_event_id: Mapped[str | None] = mapped_column(Text)
    external_reference: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(200))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # All-day events are stored at midnight UTC of their calendar dates.
    is_all_day: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    location_label: Mapped[str | None] = mapped_column(String(160))
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
        UniqueConstraint("user_id", "forecast_at", name="weather_user_forecast_at"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    location_label: Mapped[str] = mapped_column(String(160))
    # A daily forecast is stored at midnight UTC of its local calendar date.
    forecast_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # The day's high; `temperature_min_celsius` is its low.
    temperature_celsius: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    temperature_min_celsius: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    humidity: Mapped[int | None]
    precipitation_probability: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    weather_code: Mapped[int | None]
    condition: Mapped[str] = mapped_column(String(40))
    source: Mapped[str] = mapped_column(String(80))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Recommendation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 100", name="score_range"),
        CheckConstraint("recommended_sprays BETWEEN 1 AND 30", name="recommended_sprays_range"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    recommended_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    context: Mapped[str] = mapped_column(String(40))
    fragrance_id: Mapped[UUID] = mapped_column(ForeignKey("fragrances.id", ondelete="CASCADE"))
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
    fragrance_id: Mapped[UUID] = mapped_column(ForeignKey("fragrances.id", ondelete="CASCADE"))
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

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    primary_fragrance_id: Mapped[UUID] = mapped_column(
        ForeignKey("fragrances.id", ondelete="CASCADE")
    )
    secondary_fragrance_id: Mapped[UUID] = mapped_column(
        ForeignKey("fragrances.id", ondelete="CASCADE")
    )
    worn_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    rating: Mapped[int | None]
    notes: Mapped[str | None]
