"""Add source-backed shared catalog import schema.

Revision ID: 20260925_0004
Revises: 20260923_0003
"""

import re
import unicodedata
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260925_0004"
down_revision: str | Sequence[str] | None = "20260923_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.replace("&", " and "))
    without_marks = "".join(char for char in normalized if not unicodedata.combining(char))
    return _NON_ALPHANUMERIC.sub(" ", without_marks.casefold()).strip()


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

    op.drop_constraint(op.f("uq_notes_name"), "notes", type_="unique")

    op.add_column("brands", sa.Column("country", sa.String(length=80), nullable=True))

    op.alter_column(
        "fragrances",
        "name",
        existing_type=sa.String(length=160),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
    op.alter_column(
        "fragrances",
        "concentration",
        existing_type=sa.String(length=40),
        nullable=True,
    )
    for column in (
        sa.Column("gender", sa.String(length=10), nullable=True),
        sa.Column("olfactory_family", sa.String(length=60), nullable=True),
        sa.Column("product_line", sa.String(length=160), nullable=True),
        sa.Column("image_url", sa.String(length=512), nullable=True),
        sa.Column("rating_average", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("rating_count", sa.Integer(), nullable=True),
        sa.Column("popularity_score", sa.Integer(), nullable=True),
        sa.Column("search_text", sa.String(), nullable=True),
    ):
        op.add_column("fragrances", column)

    connection = op.get_bind()
    legacy_rows = connection.execute(
        sa.text(
            "SELECT f.id, b.name AS brand, f.name, f.concentration "
            "FROM fragrances f JOIN brands b ON b.id = f.brand_id"
        )
    ).mappings()
    search_documents = [
        {
            "id": row["id"],
            "search_text": _fold(
                " ".join(
                    value for value in (row["brand"], row["name"], row["concentration"]) if value
                )
            ),
        }
        for row in legacy_rows
    ]
    if search_documents:
        connection.execute(
            sa.text("UPDATE fragrances SET search_text = :search_text WHERE id = :id"),
            search_documents,
        )

    op.create_check_constraint(
        "gender_value",
        "fragrances",
        "gender IS NULL OR gender IN ('male', 'female', 'unisex')",
    )
    op.create_check_constraint(
        "rating_average_range",
        "fragrances",
        "rating_average IS NULL OR rating_average BETWEEN 0 AND 5",
    )
    op.create_check_constraint(
        "rating_count_nonnegative",
        "fragrances",
        "rating_count IS NULL OR rating_count >= 0",
    )
    op.create_check_constraint(
        "popularity_score_nonnegative",
        "fragrances",
        "popularity_score IS NULL OR popularity_score >= 0",
    )
    op.drop_index("uq_fragrances_shared_identity", table_name="fragrances")
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX uq_fragrances_shared_identity ON fragrances "
            "(brand_id, lower(name), concentration, release_year, gender) "
            "NULLS NOT DISTINCT WHERE owner_user_id IS NULL"
        )
    )
    op.create_index(
        "ix_fragrances_popularity_score_desc",
        "fragrances",
        [sa.text("popularity_score DESC")],
    )
    op.create_index(
        "ix_fragrances_search_text_trgm",
        "fragrances",
        ["search_text"],
        postgresql_using="gin",
        postgresql_ops={"search_text": "gin_trgm_ops"},
    )

    op.add_column(
        "fragrance_notes",
        sa.Column("weight", sa.Numeric(precision=3, scale=2), nullable=True),
    )
    op.drop_constraint(op.f("ck_fragrance_notes_stage_value"), "fragrance_notes", type_="check")
    op.create_check_constraint(
        "stage_value",
        "fragrance_notes",
        "stage IN ('top', 'middle', 'base', 'general')",
    )
    op.create_check_constraint(
        "weight_range",
        "fragrance_notes",
        "weight IS NULL OR weight BETWEEN 0 AND 1",
    )

    op.create_table(
        "perfumers",
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_perfumers")),
        sa.UniqueConstraint("slug", name=op.f("uq_perfumers_slug")),
    )
    op.create_table(
        "catalog_import_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("counts", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name=op.f("ck_catalog_import_runs_status_value"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_catalog_import_runs")),
    )
    op.create_table(
        "fragrance_perfumers",
        sa.Column("fragrance_id", sa.Uuid(), nullable=False),
        sa.Column("perfumer_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["fragrance_id"],
            ["fragrances.id"],
            name=op.f("fk_fragrance_perfumers_fragrance_id_fragrances"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["perfumer_id"],
            ["perfumers.id"],
            name=op.f("fk_fragrance_perfumers_perfumer_id_perfumers"),
        ),
        sa.PrimaryKeyConstraint("fragrance_id", "perfumer_id", name=op.f("pk_fragrance_perfumers")),
    )
    op.create_table(
        "fragrance_community_stats",
        sa.Column("fragrance_id", sa.Uuid(), nullable=False),
        sa.Column("longevity_average", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("longevity_votes", sa.Integer(), nullable=True),
        sa.Column("sillage_average", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("sillage_votes", sa.Integer(), nullable=True),
        sa.Column("price_value_average", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("price_value_votes", sa.Integer(), nullable=True),
        sa.Column("have_count", sa.Integer(), nullable=True),
        sa.Column("had_count", sa.Integer(), nullable=True),
        sa.Column("want_count", sa.Integer(), nullable=True),
        sa.Column("perceived_female", sa.Integer(), nullable=True),
        sa.Column("perceived_female_leaning", sa.Integer(), nullable=True),
        sa.Column("perceived_unisex", sa.Integer(), nullable=True),
        sa.Column("perceived_male_leaning", sa.Integer(), nullable=True),
        sa.Column("perceived_male", sa.Integer(), nullable=True),
        sa.Column("day_votes", sa.Integer(), nullable=True),
        sa.Column("night_votes", sa.Integer(), nullable=True),
        sa.Column("voters", sa.Integer(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "longevity_average IS NULL OR longevity_average BETWEEN 1 AND 5",
            name=op.f("ck_fragrance_community_stats_longevity_average_range"),
        ),
        sa.CheckConstraint(
            "sillage_average IS NULL OR sillage_average BETWEEN 1 AND 4",
            name=op.f("ck_fragrance_community_stats_sillage_average_range"),
        ),
        sa.CheckConstraint(
            "price_value_average IS NULL OR price_value_average BETWEEN 1 AND 5",
            name=op.f("ck_fragrance_community_stats_price_value_average_range"),
        ),
        sa.ForeignKeyConstraint(
            ["fragrance_id"],
            ["fragrances.id"],
            name=op.f("fk_fragrance_community_stats_fragrance_id_fragrances"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("fragrance_id", name=op.f("pk_fragrance_community_stats")),
    )
    op.create_table(
        "fragrance_similarities",
        sa.Column("fragrance_id", sa.Uuid(), nullable=False),
        sa.Column("similar_fragrance_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("up_votes", sa.Integer(), nullable=True),
        sa.Column("down_votes", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "fragrance_id <> similar_fragrance_id",
            name=op.f("ck_fragrance_similarities_distinct_fragrances"),
        ),
        sa.CheckConstraint(
            "kind IN ('reminds_me_of', 'also_liked')",
            name=op.f("ck_fragrance_similarities_kind_value"),
        ),
        sa.CheckConstraint("rank > 0", name=op.f("ck_fragrance_similarities_rank_positive")),
        sa.ForeignKeyConstraint(
            ["fragrance_id"],
            ["fragrances.id"],
            name=op.f("fk_fragrance_similarities_fragrance_id_fragrances"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["similar_fragrance_id"],
            ["fragrances.id"],
            name=op.f("fk_fragrance_similarities_similar_fragrance_id_fragrances"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "fragrance_id",
            "similar_fragrance_id",
            "kind",
            name=op.f("pk_fragrance_similarities"),
        ),
    )
    op.create_index(
        "ix_fragrance_similarities_similar_fragrance_id",
        "fragrance_similarities",
        ["similar_fragrance_id"],
    )
    op.create_table(
        "fragrance_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("fragrance_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("source_record_id", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=512), nullable=True),
        sa.Column("raw_name", sa.String(length=255), nullable=True),
        sa.Column("raw_brand", sa.String(length=120), nullable=True),
        sa.Column("rating_raw", sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column("rating_scale", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("rating_count", sa.Integer(), nullable=True),
        sa.Column("field_origins", sa.JSON(), nullable=False),
        sa.Column("import_run_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "source IN ('fragrantica', 'fra_cleaned', 'fra_perfumes', 'parfumo', 'luckyscent')",
            name=op.f("ck_fragrance_sources_source_value"),
        ),
        sa.CheckConstraint(
            "rating_scale IS NULL OR rating_scale > 0",
            name=op.f("ck_fragrance_sources_rating_scale_positive"),
        ),
        sa.CheckConstraint(
            "rating_count IS NULL OR rating_count >= 0",
            name=op.f("ck_fragrance_sources_rating_count_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["fragrance_id"],
            ["fragrances.id"],
            name=op.f("fk_fragrance_sources_fragrance_id_fragrances"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["import_run_id"],
            ["catalog_import_runs.id"],
            name=op.f("fk_fragrance_sources_import_run_id_catalog_import_runs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fragrance_sources")),
        sa.UniqueConstraint("source", "source_record_id", name="source_record"),
    )
    op.create_index(
        op.f("ix_fragrance_sources_fragrance_id"),
        "fragrance_sources",
        ["fragrance_id"],
    )
    op.create_index(
        op.f("ix_fragrance_sources_import_run_id"),
        "fragrance_sources",
        ["import_run_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_fragrance_sources_import_run_id"), table_name="fragrance_sources")
    op.drop_index(op.f("ix_fragrance_sources_fragrance_id"), table_name="fragrance_sources")
    op.drop_table("fragrance_sources")
    op.drop_index(
        "ix_fragrance_similarities_similar_fragrance_id",
        table_name="fragrance_similarities",
    )
    op.drop_table("fragrance_similarities")
    op.drop_table("fragrance_community_stats")
    op.drop_table("fragrance_perfumers")
    op.drop_table("catalog_import_runs")
    op.drop_table("perfumers")

    op.drop_constraint(op.f("ck_fragrance_notes_weight_range"), "fragrance_notes", type_="check")
    op.drop_constraint(op.f("ck_fragrance_notes_stage_value"), "fragrance_notes", type_="check")
    op.create_check_constraint(
        "stage_value",
        "fragrance_notes",
        "stage IN ('top', 'middle', 'base')",
    )
    op.drop_column("fragrance_notes", "weight")

    op.drop_index("ix_fragrances_search_text_trgm", table_name="fragrances")
    op.drop_index("ix_fragrances_popularity_score_desc", table_name="fragrances")
    op.drop_index("uq_fragrances_shared_identity", table_name="fragrances")
    op.create_index(
        "uq_fragrances_shared_identity",
        "fragrances",
        ["brand_id", "name", "concentration"],
        unique=True,
        postgresql_where=sa.text("owner_user_id IS NULL"),
    )
    op.drop_constraint(
        op.f("ck_fragrances_popularity_score_nonnegative"), "fragrances", type_="check"
    )
    op.drop_constraint(op.f("ck_fragrances_rating_count_nonnegative"), "fragrances", type_="check")
    op.drop_constraint(op.f("ck_fragrances_rating_average_range"), "fragrances", type_="check")
    op.drop_constraint(op.f("ck_fragrances_gender_value"), "fragrances", type_="check")
    for column in (
        "search_text",
        "popularity_score",
        "rating_count",
        "rating_average",
        "image_url",
        "product_line",
        "olfactory_family",
        "gender",
    ):
        op.drop_column("fragrances", column)
    op.alter_column(
        "fragrances",
        "concentration",
        existing_type=sa.String(length=40),
        nullable=False,
    )
    op.alter_column(
        "fragrances",
        "name",
        existing_type=sa.String(length=255),
        type_=sa.String(length=160),
        existing_nullable=False,
    )

    op.drop_column("brands", "country")

    op.create_unique_constraint(op.f("uq_notes_name"), "notes", ["name"])
