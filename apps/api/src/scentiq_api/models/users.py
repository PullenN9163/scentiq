from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from scentiq_api.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from scentiq_api.models.catalog import Fragrance


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    preferences: Mapped[UserPreference | None] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    collection_items: Mapped[list[UserCollectionItem]] = relationship(back_populates="user")


class UserPreference(TimestampMixin, Base):
    __tablename__ = "user_preferences"
    __table_args__ = (
        CheckConstraint(
            "preferred_season IS NULL OR preferred_season IN "
            "('spring', 'summer', 'fall', 'winter')",
            name="preferred_season_value",
        ),
        CheckConstraint(
            "preferred_projection IS NULL OR preferred_projection IN "
            "('intimate', 'moderate', 'strong')",
            name="preferred_projection_value",
        ),
        CheckConstraint(
            "preferred_longevity IS NULL OR preferred_longevity BETWEEN 0 AND 10",
            name="preferred_longevity_range",
        ),
        CheckConstraint(
            "maximum_sprays IS NULL OR maximum_sprays BETWEEN 1 AND 20",
            name="maximum_sprays_range",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    preferred_season: Mapped[str | None] = mapped_column(String(10))
    preferred_occasion: Mapped[str | None] = mapped_column(String(20))
    preferred_projection: Mapped[str | None] = mapped_column(String(20))
    preferred_longevity: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    maximum_sprays: Mapped[int | None]

    user: Mapped[User] = relationship(back_populates="preferences")


class UserCollectionItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_collection"
    __table_args__ = (
        CheckConstraint(
            "ownership_type IN ('bottle', 'decant', 'sample')",
            name="ownership_type_value",
        ),
        CheckConstraint(
            "status IN ('owned', 'wishlist', 'finished', 'sold')",
            name="status_value",
        ),
        CheckConstraint(
            "bottle_size_ml IS NULL OR bottle_size_ml > 0", name="bottle_size_positive"
        ),
        CheckConstraint("remaining_ml IS NULL OR remaining_ml >= 0", name="remaining_nonnegative"),
        CheckConstraint(
            "purchase_price IS NULL OR purchase_price >= 0", name="purchase_price_nonnegative"
        ),
        CheckConstraint("user_rating IS NULL OR user_rating BETWEEN 1 AND 5", name="rating_range"),
        CheckConstraint(
            "custom_longevity IS NULL OR custom_longevity BETWEEN 0 AND 10",
            name="custom_longevity_range",
        ),
        CheckConstraint(
            "custom_projection IS NULL OR custom_projection IN ('intimate', 'moderate', 'strong')",
            name="custom_projection_value",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    fragrance_id: Mapped[UUID] = mapped_column(ForeignKey("fragrances.id"), index=True)
    ownership_type: Mapped[str] = mapped_column(String(10))
    bottle_size_ml: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    remaining_ml: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    purchase_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    purchase_date: Mapped[date | None] = mapped_column(Date)
    user_rating: Mapped[int | None]
    custom_longevity: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    custom_projection: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(10))

    user: Mapped[User] = relationship(back_populates="collection_items")
    fragrance: Mapped[Fragrance] = relationship()


class WearLog(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "wear_logs"
    __table_args__ = (
        CheckConstraint("sprays IS NULL OR sprays BETWEEN 1 AND 30", name="sprays_range"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    collection_item_id: Mapped[UUID] = mapped_column(ForeignKey("user_collection.id"))
    worn_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sprays: Mapped[int | None]
    occasion: Mapped[str | None] = mapped_column(String(20))
    setting: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str | None]


class WearFeedback(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "wear_feedback"
    __table_args__ = (
        CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="rating_range"),
        CheckConstraint("longevity IS NULL OR longevity BETWEEN 0 AND 10", name="longevity_range"),
        CheckConstraint(
            "projection IS NULL OR projection IN ('intimate', 'moderate', 'strong')",
            name="projection_value",
        ),
    )

    wear_log_id: Mapped[UUID] = mapped_column(ForeignKey("wear_logs.id"), unique=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    rating: Mapped[int | None]
    longevity: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    projection: Mapped[str | None] = mapped_column(String(20))
    comments: Mapped[str | None]


class Wishlist(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "wishlists"
    __table_args__ = (
        CheckConstraint("priority BETWEEN 1 AND 5", name="priority_range"),
        UniqueConstraint("user_id", "fragrance_id", name="wishlist_user_fragrance"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=False)
    fragrance_id: Mapped[UUID] = mapped_column(ForeignKey("fragrances.id"), primary_key=False)
    priority: Mapped[int]
    reason: Mapped[str | None]
