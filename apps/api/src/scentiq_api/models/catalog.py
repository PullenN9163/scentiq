from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
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
    country: Mapped[str | None] = mapped_column(String(80))
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
            text("lower(name)"),
            "concentration",
            "release_year",
            "gender",
            unique=True,
            postgresql_where="owner_user_id IS NULL",
            postgresql_nulls_not_distinct=True,
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
        CheckConstraint(
            "gender IS NULL OR gender IN ('male', 'female', 'unisex')",
            name="gender_value",
        ),
        CheckConstraint(
            "rating_average IS NULL OR rating_average BETWEEN 0 AND 5",
            name="rating_average_range",
        ),
        CheckConstraint(
            "rating_count IS NULL OR rating_count >= 0",
            name="rating_count_nonnegative",
        ),
        CheckConstraint(
            "popularity_score IS NULL OR popularity_score >= 0",
            name="popularity_score_nonnegative",
        ),
        Index("ix_fragrances_popularity_score_desc", text("popularity_score DESC")),
        Index(
            "ix_fragrances_search_text_trgm",
            "search_text",
            postgresql_using="gin",
            postgresql_ops={"search_text": "gin_trgm_ops"},
        ),
    )

    brand_id: Mapped[UUID] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    owner_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), index=True)
    concentration: Mapped[str | None] = mapped_column(String(40))
    release_year: Mapped[int | None]
    description: Mapped[str | None]
    image_blob_path: Mapped[str | None] = mapped_column(String(512))
    image_url: Mapped[str | None] = mapped_column(String(512))
    gender: Mapped[str | None] = mapped_column(String(10))
    olfactory_family: Mapped[str | None] = mapped_column(String(60))
    product_line: Mapped[str | None] = mapped_column(String(160))
    rating_average: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    rating_count: Mapped[int | None]
    popularity_score: Mapped[int | None] = mapped_column(Integer)
    search_text: Mapped[str | None] = mapped_column(String)
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
    perfumer_links: Mapped[list[FragrancePerfumer]] = relationship(
        back_populates="fragrance", cascade="all, delete-orphan"
    )
    community: Mapped[FragranceCommunityStats | None] = relationship(
        back_populates="fragrance", cascade="all, delete-orphan"
    )
    source_links: Mapped[list[FragranceSource]] = relationship(
        back_populates="fragrance", cascade="all, delete-orphan"
    )


class Note(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notes"

    name: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    fragrance_links: Mapped[list[FragranceNote]] = relationship(back_populates="note")


class FragranceNote(Base):
    __tablename__ = "fragrance_notes"
    __table_args__ = (
        CheckConstraint("stage IN ('top', 'middle', 'base', 'general')", name="stage_value"),
        CheckConstraint("weight IS NULL OR weight BETWEEN 0 AND 1", name="weight_range"),
    )

    fragrance_id: Mapped[UUID] = mapped_column(
        ForeignKey("fragrances.id", ondelete="CASCADE"), primary_key=True
    )
    note_id: Mapped[UUID] = mapped_column(ForeignKey("notes.id"), primary_key=True)
    stage: Mapped[str] = mapped_column(String(10), primary_key=True)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))

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


class Perfumer(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "perfumers"

    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(160), unique=True)
    fragrance_links: Mapped[list[FragrancePerfumer]] = relationship(back_populates="perfumer")


class FragrancePerfumer(Base):
    __tablename__ = "fragrance_perfumers"

    fragrance_id: Mapped[UUID] = mapped_column(
        ForeignKey("fragrances.id", ondelete="CASCADE"), primary_key=True
    )
    perfumer_id: Mapped[UUID] = mapped_column(ForeignKey("perfumers.id"), primary_key=True)

    fragrance: Mapped[Fragrance] = relationship(back_populates="perfumer_links")
    perfumer: Mapped[Perfumer] = relationship(back_populates="fragrance_links")


class FragranceCommunityStats(Base):
    __tablename__ = "fragrance_community_stats"
    __table_args__ = (
        CheckConstraint(
            "longevity_average IS NULL OR longevity_average BETWEEN 1 AND 5",
            name="longevity_average_range",
        ),
        CheckConstraint(
            "sillage_average IS NULL OR sillage_average BETWEEN 1 AND 4",
            name="sillage_average_range",
        ),
        CheckConstraint(
            "price_value_average IS NULL OR price_value_average BETWEEN 1 AND 5",
            name="price_value_average_range",
        ),
    )

    fragrance_id: Mapped[UUID] = mapped_column(
        ForeignKey("fragrances.id", ondelete="CASCADE"), primary_key=True
    )
    longevity_average: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    longevity_votes: Mapped[int | None]
    sillage_average: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    sillage_votes: Mapped[int | None]
    price_value_average: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    price_value_votes: Mapped[int | None]
    have_count: Mapped[int | None]
    had_count: Mapped[int | None]
    want_count: Mapped[int | None]
    perceived_female: Mapped[int | None]
    perceived_female_leaning: Mapped[int | None]
    perceived_unisex: Mapped[int | None]
    perceived_male_leaning: Mapped[int | None]
    perceived_male: Mapped[int | None]
    day_votes: Mapped[int | None]
    night_votes: Mapped[int | None]
    voters: Mapped[int | None]
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    fragrance: Mapped[Fragrance] = relationship(back_populates="community")


class FragranceSimilarity(Base):
    __tablename__ = "fragrance_similarities"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('reminds_me_of', 'also_liked')",
            name="kind_value",
        ),
        CheckConstraint(
            "fragrance_id <> similar_fragrance_id",
            name="distinct_fragrances",
        ),
        CheckConstraint("rank > 0", name="rank_positive"),
        Index("ix_fragrance_similarities_similar_fragrance_id", "similar_fragrance_id"),
    )

    fragrance_id: Mapped[UUID] = mapped_column(
        ForeignKey("fragrances.id", ondelete="CASCADE"), primary_key=True
    )
    similar_fragrance_id: Mapped[UUID] = mapped_column(
        ForeignKey("fragrances.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(20), primary_key=True)
    rank: Mapped[int]
    up_votes: Mapped[int | None]
    down_votes: Mapped[int | None]


class CatalogImportRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "catalog_import_runs"
    __table_args__ = (
        CheckConstraint("status IN ('running', 'succeeded', 'failed')", name="status_value"),
    )

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20))
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON)
    counts: Mapped[dict[str, Any]] = mapped_column(JSON)
    source_links: Mapped[list[FragranceSource]] = relationship(back_populates="import_run")


class FragranceSource(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "fragrance_sources"
    __table_args__ = (
        CheckConstraint(
            "source IN ('fragrantica', 'fra_cleaned', 'fra_perfumes', 'parfumo', 'luckyscent')",
            name="source_value",
        ),
        CheckConstraint(
            "rating_scale IS NULL OR rating_scale > 0",
            name="rating_scale_positive",
        ),
        CheckConstraint(
            "rating_count IS NULL OR rating_count >= 0",
            name="rating_count_nonnegative",
        ),
        UniqueConstraint("source", "source_record_id", name="source_record"),
    )

    fragrance_id: Mapped[UUID] = mapped_column(
        ForeignKey("fragrances.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(20))
    source_record_id: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(512))
    raw_name: Mapped[str | None] = mapped_column(String(255))
    raw_brand: Mapped[str | None] = mapped_column(String(120))
    rating_raw: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    rating_scale: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    rating_count: Mapped[int | None]
    field_origins: Mapped[dict[str, str]] = mapped_column(JSON)
    import_run_id: Mapped[UUID] = mapped_column(ForeignKey("catalog_import_runs.id"), index=True)

    fragrance: Mapped[Fragrance] = relationship(back_populates="source_links")
    import_run: Mapped[CatalogImportRun] = relationship(back_populates="source_links")
