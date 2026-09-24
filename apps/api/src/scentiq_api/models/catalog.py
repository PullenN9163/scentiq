from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from scentiq_api.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Brand(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A fragrance house. Rows with a NULL owner are shared curated records."""

    __tablename__ = "brands"
    __table_args__ = (
        Index(
            "uq_brands_shared_name",
            "name",
            unique=True,
            postgresql_where="owner_user_id IS NULL",
        ),
        Index(
            "uq_brands_shared_slug",
            "slug",
            unique=True,
            postgresql_where="owner_user_id IS NULL",
        ),
        Index(
            "uq_brands_custom_name",
            "owner_user_id",
            "name",
            unique=True,
            postgresql_where="owner_user_id IS NOT NULL",
        ),
    )

    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120))
    owner_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    fragrances: Mapped[list[Fragrance]] = relationship(back_populates="brand")


class Fragrance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A fragrance. Rows with a NULL owner are shared curated records."""

    __tablename__ = "fragrances"
    __table_args__ = (
        Index(
            "uq_fragrances_shared_identity",
            "brand_id",
            "name",
            "concentration",
            unique=True,
            postgresql_where="owner_user_id IS NULL",
        ),
        Index(
            "uq_fragrances_custom_identity",
            "owner_user_id",
            "brand_id",
            "name",
            "concentration",
            unique=True,
            postgresql_where="owner_user_id IS NOT NULL",
        ),
        CheckConstraint(
            "release_year IS NULL OR release_year BETWEEN 1700 AND 2100",
            name="release_year_range",
        ),
        CheckConstraint(
            "longevity_score IS NULL OR longevity_score BETWEEN 0 AND 10",
            name="longevity_score_range",
        ),
        CheckConstraint(
            "projection_level IS NULL OR projection_level IN ('intimate', 'moderate', 'strong')",
            name="projection_level_value",
        ),
    )

    brand_id: Mapped[UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    owner_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160), index=True)
    concentration: Mapped[str] = mapped_column(String(40))
    release_year: Mapped[int | None]
    description: Mapped[str | None]
    image_blob_path: Mapped[str | None] = mapped_column(String(512))
    longevity_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    projection_level: Mapped[str | None] = mapped_column(String(20))

    brand: Mapped[Brand] = relationship(back_populates="fragrances")
    note_links: Mapped[list[FragranceNote]] = relationship(
        back_populates="fragrance", cascade="all, delete-orphan"
    )
    accord_links: Mapped[list[FragranceAccord]] = relationship(
        back_populates="fragrance", cascade="all, delete-orphan"
    )
    seasons: Mapped[list[FragranceSeason]] = relationship(
        back_populates="fragrance", cascade="all, delete-orphan"
    )
    occasions: Mapped[list[FragranceOccasion]] = relationship(
        back_populates="fragrance", cascade="all, delete-orphan"
    )


class Note(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notes"

    name: Mapped[str] = mapped_column(String(100), unique=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    fragrance_links: Mapped[list[FragranceNote]] = relationship(back_populates="note")


class FragranceNote(Base):
    __tablename__ = "fragrance_notes"
    __table_args__ = (CheckConstraint("stage IN ('top', 'middle', 'base')", name="stage_value"),)

    fragrance_id: Mapped[UUID] = mapped_column(
        ForeignKey("fragrances.id", ondelete="CASCADE"), primary_key=True
    )
    note_id: Mapped[UUID] = mapped_column(ForeignKey("notes.id"), primary_key=True)
    stage: Mapped[str] = mapped_column(String(10), primary_key=True)

    fragrance: Mapped[Fragrance] = relationship(back_populates="note_links")
    note: Mapped[Note] = relationship(back_populates="fragrance_links")


class Accord(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "accords"

    name: Mapped[str] = mapped_column(String(100), unique=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    fragrance_links: Mapped[list[FragranceAccord]] = relationship(back_populates="accord")


class FragranceAccord(Base):
    __tablename__ = "fragrance_accords"
    __table_args__ = (CheckConstraint("weight BETWEEN 0 AND 1", name="weight_range"),)

    fragrance_id: Mapped[UUID] = mapped_column(
        ForeignKey("fragrances.id", ondelete="CASCADE"), primary_key=True
    )
    accord_id: Mapped[UUID] = mapped_column(ForeignKey("accords.id"), primary_key=True)
    weight: Mapped[Decimal] = mapped_column(Numeric(3, 2))

    fragrance: Mapped[Fragrance] = relationship(back_populates="accord_links")
    accord: Mapped[Accord] = relationship(back_populates="fragrance_links")


class FragranceSeason(Base):
    __tablename__ = "fragrance_seasons"
    __table_args__ = (
        CheckConstraint("season IN ('spring', 'summer', 'fall', 'winter')", name="season_value"),
        CheckConstraint("weight BETWEEN 0 AND 1", name="weight_range"),
    )

    fragrance_id: Mapped[UUID] = mapped_column(
        ForeignKey("fragrances.id", ondelete="CASCADE"), primary_key=True
    )
    season: Mapped[str] = mapped_column(String(10), primary_key=True)
    weight: Mapped[Decimal] = mapped_column(Numeric(3, 2))

    fragrance: Mapped[Fragrance] = relationship(back_populates="seasons")


class FragranceOccasion(Base):
    __tablename__ = "fragrance_occasions"
    __table_args__ = (
        CheckConstraint(
            "occasion IN "
            "('work', 'casual', 'date', 'dinner', 'party', 'formal', 'gym', 'travel', 'other')",
            name="occasion_value",
        ),
        CheckConstraint("weight BETWEEN 0 AND 1", name="weight_range"),
    )

    fragrance_id: Mapped[UUID] = mapped_column(
        ForeignKey("fragrances.id", ondelete="CASCADE"), primary_key=True
    )
    occasion: Mapped[str] = mapped_column(String(10), primary_key=True)
    weight: Mapped[Decimal] = mapped_column(Numeric(3, 2))

    fragrance: Mapped[Fragrance] = relationship(back_populates="occasions")
