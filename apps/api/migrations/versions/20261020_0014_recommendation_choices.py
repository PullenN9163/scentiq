"""Persist recommendation browsing, retry receipts, and reasoned feedback."""

import sqlalchemy as sa
from alembic import op

revision = "20261020_0014"
down_revision = "20261020_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recommendation_choices",
        sa.Column(
            "recommendation_id",
            sa.Uuid(),
            sa.ForeignKey("recommendations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "selected_fragrance_id",
            sa.Uuid(),
            sa.ForeignKey("fragrances.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seen_ids", sa.JSON(), nullable=False),
    )
    op.create_table(
        "recommendation_choice_receipts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "recommendation_id",
            sa.Uuid(),
            sa.ForeignKey("recommendations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("reset", sa.Boolean(), nullable=False),
        sa.Column("expected_fragrance_id", sa.Uuid(), nullable=True),
        sa.Column("response_data", sa.JSON(), nullable=False),
        sa.UniqueConstraint("recommendation_id", "idempotency_key"),
    )
    op.create_table(
        "recommendation_feedback",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "recommendation_id",
            sa.Uuid(),
            sa.ForeignKey("recommendations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "fragrance_id",
            sa.Uuid(),
            sa.ForeignKey("fragrances.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(24), nullable=False),
    )
    op.create_index("ix_recommendation_feedback_user_id", "recommendation_feedback", ["user_id"])

    op.create_table(
        "surface_choice_batches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("surface", sa.String(16), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("candidates", sa.JSON(), nullable=False),
        sa.Column("selected_key", sa.String(120)),
        sa.Column("seen_keys", sa.JSON(), nullable=False),
        sa.UniqueConstraint("user_id", "surface", "fingerprint"),
    )
    op.create_index("ix_surface_choice_batches_user_id", "surface_choice_batches", ["user_id"])
    op.create_table(
        "surface_choice_receipts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "batch_id",
            sa.Uuid(),
            sa.ForeignKey("surface_choice_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("response_data", sa.JSON(), nullable=False),
        sa.UniqueConstraint("batch_id", "idempotency_key"),
    )


def downgrade() -> None:
    op.drop_table("surface_choice_receipts")
    op.drop_table("surface_choice_batches")
    op.drop_table("recommendation_feedback")
    op.drop_table("recommendation_choice_receipts")
    op.drop_table("recommendation_choices")
