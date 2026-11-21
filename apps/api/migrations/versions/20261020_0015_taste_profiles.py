"""Explicit preferences and versioned derived member taste."""

import sqlalchemy as sa
from alembic import op

revision = "20261020_0015"
down_revision = "20261020_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in (
        "liked_notes",
        "disliked_notes",
        "liked_accords",
        "disliked_accords",
        "liked_families",
        "disliked_families",
        "excluded_fragrance_ids",
    ):
        op.add_column(
            "user_preferences", sa.Column(name, sa.JSON(), nullable=False, server_default="[]")
        )
    op.add_column(
        "user_preferences",
        sa.Column("variety_preference", sa.String(20), nullable=False, server_default="balanced"),
    )
    op.add_column(
        "user_preferences",
        sa.Column(
            "calendar_ai_titles_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.create_table(
        "user_taste_profiles",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.drop_table("user_taste_profiles")
    for name in (
        "liked_notes",
        "disliked_notes",
        "liked_accords",
        "disliked_accords",
        "liked_families",
        "disliked_families",
        "excluded_fragrance_ids",
        "variety_preference",
        "calendar_ai_titles_enabled",
    ):
        op.drop_column("user_preferences", name)
