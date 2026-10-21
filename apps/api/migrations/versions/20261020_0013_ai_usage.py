"""Global inference ledger and member-scoped ranking cache."""

import sqlalchemy as sa
from alembic import op

revision = "20261020_0013"
down_revision = "20261020_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_months",
        sa.Column("month", sa.String(7), primary_key=True),
        sa.Column("charged_microusd", sa.Integer(), nullable=False),
    )
    op.create_table(
        "ai_usage_reservations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("month", sa.String(7), sa.ForeignKey("ai_usage_months.month"), nullable=False),
        sa.Column("amount_microusd", sa.Integer(), nullable=False),
        sa.Column("actual_microusd", sa.Integer(), nullable=True),
    )
    op.create_index("ix_ai_usage_reservations_month", "ai_usage_reservations", ["month"])
    op.create_table(
        "ai_ranking_cache",
        sa.Column("cache_key", sa.String(64), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ai_ranking_cache_user_id", "ai_ranking_cache", ["user_id"])


def downgrade() -> None:
    op.drop_table("ai_ranking_cache")
    op.drop_table("ai_usage_reservations")
    op.drop_table("ai_usage_months")
