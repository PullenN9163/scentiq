"""Add external identity mapping, user lifecycle state, and catalog ownership.

Revision ID: 20260923_0003
Revises: 68bfbd3cf8fb
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260923_0003"
down_revision: str | Sequence[str] | None = "68bfbd3cf8fb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, constraint name, local column, referred table)
_USER_SCOPED_FOREIGN_KEYS: tuple[tuple[str, str, str, str], ...] = (
    ("user_collection", "fk_user_collection_user_id_users", "user_id", "users"),
    (
        "user_collection",
        "fk_user_collection_fragrance_id_fragrances",
        "fragrance_id",
        "fragrances",
    ),
    ("wear_logs", "fk_wear_logs_user_id_users", "user_id", "users"),
    (
        "wear_logs",
        "fk_wear_logs_collection_item_id_user_collection",
        "collection_item_id",
        "user_collection",
    ),
    ("wear_feedback", "fk_wear_feedback_user_id_users", "user_id", "users"),
    ("wear_feedback", "fk_wear_feedback_wear_log_id_wear_logs", "wear_log_id", "wear_logs"),
    ("wishlists", "fk_wishlists_user_id_users", "user_id", "users"),
    ("wishlists", "fk_wishlists_fragrance_id_fragrances", "fragrance_id", "fragrances"),
    ("calendar_events", "fk_calendar_events_user_id_users", "user_id", "users"),
    ("weather_snapshots", "fk_weather_snapshots_user_id_users", "user_id", "users"),
    ("recommendations", "fk_recommendations_user_id_users", "user_id", "users"),
    (
        "recommendations",
        "fk_recommendations_fragrance_id_fragrances",
        "fragrance_id",
        "fragrances",
    ),
    (
        "recommendation_candidates",
        "fk_recommendation_candidates_fragrance_id_fragrances",
        "fragrance_id",
        "fragrances",
    ),
    ("layering_logs", "fk_layering_logs_user_id_users", "user_id", "users"),
    (
        "layering_logs",
        "fk_layering_logs_primary_fragrance_id_fragrances",
        "primary_fragrance_id",
        "fragrances",
    ),
    (
        "layering_logs",
        "fk_layering_logs_secondary_fragrance_id_fragrances",
        "secondary_fragrance_id",
        "fragrances",
    ),
    ("fragrances", "fk_fragrances_brand_id_brands", "brand_id", "brands"),
)

# Indexes added purely to keep the deletion cascade from sequentially scanning.
_OWNERSHIP_INDEXES: tuple[tuple[str, str, str], ...] = (
    ("ix_brands_owner_user_id", "brands", "owner_user_id"),
    ("ix_fragrances_owner_user_id", "fragrances", "owner_user_id"),
    ("ix_wishlists_user_id", "wishlists", "user_id"),
    ("ix_wishlists_fragrance_id", "wishlists", "fragrance_id"),
)


def _set_cascade(ondelete: str | None) -> None:
    for table, name, column, referred in _USER_SCOPED_FOREIGN_KEYS:
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(
            name,
            table,
            referred,
            [column],
            ["id"],
            ondelete=ondelete,
        )


def upgrade() -> None:
    # --- user lifecycle -------------------------------------------------
    op.add_column(
        "users",
        sa.Column(
            "lifecycle_state",
            sa.String(length=20),
            nullable=False,
            server_default="active",
        ),
    )
    op.add_column(
        "users",
        sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "lifecycle_state_value",
        "users",
        "lifecycle_state IN ('active', 'deletion_pending')",
    )

    # --- preferences ---------------------------------------------------
    op.add_column(
        "user_preferences",
        sa.Column("location", sa.String(length=120), nullable=True),
    )

    # --- catalog ownership ---------------------------------------------
    op.add_column("brands", sa.Column("owner_user_id", sa.Uuid(), nullable=True))
    op.add_column("fragrances", sa.Column("owner_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_brands_owner_user_id_users",
        "brands",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_fragrances_owner_user_id_users",
        "fragrances",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Global catalog uniqueness becomes partial: shared rows stay globally
    # unique, custom rows are unique only within their owner.
    op.drop_constraint("uq_brands_name", "brands", type_="unique")
    op.drop_constraint("uq_brands_slug", "brands", type_="unique")
    op.drop_constraint("fragrance_identity", "fragrances", type_="unique")

    op.create_index(
        "uq_brands_shared_name",
        "brands",
        ["name"],
        unique=True,
        postgresql_where=sa.text("owner_user_id IS NULL"),
    )
    op.create_index(
        "uq_brands_shared_slug",
        "brands",
        ["slug"],
        unique=True,
        postgresql_where=sa.text("owner_user_id IS NULL"),
    )
    op.create_index(
        "uq_brands_custom_name",
        "brands",
        ["owner_user_id", "name"],
        unique=True,
        postgresql_where=sa.text("owner_user_id IS NOT NULL"),
    )
    op.create_index(
        "uq_fragrances_shared_identity",
        "fragrances",
        ["brand_id", "name", "concentration"],
        unique=True,
        postgresql_where=sa.text("owner_user_id IS NULL"),
    )
    op.create_index(
        "uq_fragrances_custom_identity",
        "fragrances",
        ["owner_user_id", "brand_id", "name", "concentration"],
        unique=True,
        postgresql_where=sa.text("owner_user_id IS NOT NULL"),
    )

    for index_name, table, column in _OWNERSHIP_INDEXES:
        op.create_index(index_name, table, [column])

    # --- identity mapping ----------------------------------------------
    op.create_table(
        "user_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("provider IN ('clerk')", name=op.f("ck_user_identities_provider_value")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_identities_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_identities")),
        sa.UniqueConstraint("provider", "subject", name="identity_provider_subject"),
    )
    # One unique index rather than a unique constraint plus a plain index: the
    # model declares index=True with unique=True, which renders exactly this.
    op.create_index("ix_user_identities_user_id", "user_identities", ["user_id"], unique=True)

    op.create_table(
        "identity_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("provider IN ('clerk')", name=op.f("ck_identity_events_provider_value")),
        sa.CheckConstraint(
            "event_type IN ('user.deleted')",
            name=op.f("ck_identity_events_event_type_value"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_identity_events")),
        sa.UniqueConstraint("provider", "event_id", name="identity_event_provider_event"),
    )
    op.create_index("ix_identity_events_subject", "identity_events", ["subject"])

    # --- deletion behaviour --------------------------------------------
    _set_cascade("CASCADE")


def downgrade() -> None:
    _set_cascade(None)

    op.drop_index("ix_identity_events_subject", table_name="identity_events")
    op.drop_table("identity_events")
    op.drop_index("ix_user_identities_user_id", table_name="user_identities")
    op.drop_table("user_identities")

    for index_name, table, _ in reversed(_OWNERSHIP_INDEXES):
        op.drop_index(index_name, table_name=table)

    op.drop_index("uq_fragrances_custom_identity", table_name="fragrances")
    op.drop_index("uq_fragrances_shared_identity", table_name="fragrances")
    op.drop_index("uq_brands_custom_name", table_name="brands")
    op.drop_index("uq_brands_shared_slug", table_name="brands")
    op.drop_index("uq_brands_shared_name", table_name="brands")

    # Restoring global uniqueness requires the custom rows to be gone first.
    op.execute(sa.text("DELETE FROM fragrances WHERE owner_user_id IS NOT NULL"))
    op.execute(sa.text("DELETE FROM brands WHERE owner_user_id IS NOT NULL"))

    op.create_unique_constraint(
        "fragrance_identity", "fragrances", ["brand_id", "name", "concentration"]
    )
    op.create_unique_constraint("uq_brands_slug", "brands", ["slug"])
    op.create_unique_constraint("uq_brands_name", "brands", ["name"])

    op.drop_constraint("fk_fragrances_owner_user_id_users", "fragrances", type_="foreignkey")
    op.drop_constraint("fk_brands_owner_user_id_users", "brands", type_="foreignkey")
    op.drop_column("fragrances", "owner_user_id")
    op.drop_column("brands", "owner_user_id")

    op.drop_column("user_preferences", "location")

    # op.f() marks the name as final. The "ck" naming convention interpolates
    # %(constraint_name)s, so a bare or already-prefixed name would be expanded
    # again into ck_users_ck_users_lifecycle_state_value.
    op.drop_constraint(op.f("ck_users_lifecycle_state_value"), "users", type_="check")
    op.drop_column("users", "deletion_requested_at")
    op.drop_column("users", "lifecycle_state")
