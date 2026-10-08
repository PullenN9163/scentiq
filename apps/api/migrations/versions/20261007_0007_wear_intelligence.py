"""Persisted wear recommendation inputs, decisions and wear linkage."""

import sqlalchemy as sa
from alembic import op

revision = "20261007_0007_wear_intelligence"
down_revision = "20261005_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("recommendations", sa.Column("context_key", sa.String(160)))
    op.add_column("recommendations", sa.Column("calendar_event_id", sa.Uuid()))
    op.add_column("recommendations", sa.Column("input_fingerprint", sa.String(64)))
    op.add_column(
        "recommendations", sa.Column("context_data", sa.JSON(), nullable=False, server_default="{}")
    )
    op.add_column(
        "recommendations",
        sa.Column("score_components", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "recommendations",
        sa.Column("evidence_coverage", sa.Numeric(5, 4), nullable=False, server_default="0"),
    )
    op.create_foreign_key(
        "fk_recommendations_calendar_event_id_calendar_events",
        "recommendations",
        "calendar_events",
        ["calendar_event_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_recommendations_context_key", "recommendations", ["context_key"])
    op.create_unique_constraint(
        "wear_recommendation_inputs",
        "recommendations",
        ["user_id", "context_key", "input_fingerprint", "algorithm_version"],
    )
    op.create_check_constraint(
        "evidence_coverage_range", "recommendations", "evidence_coverage BETWEEN 0 AND 1"
    )
    op.add_column(
        "recommendation_candidates",
        sa.Column("guidance", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column("wear_logs", sa.Column("recommendation_id", sa.Uuid()))
    op.create_foreign_key(
        "fk_wear_logs_recommendation_id_recommendations",
        "wear_logs",
        "recommendations",
        ["recommendation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_wear_logs_recommendation_id", "wear_logs", ["recommendation_id"])
    op.create_table(
        "recommendation_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "recommendation_id",
            sa.Uuid(),
            sa.ForeignKey("recommendations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column(
            "selected_fragrance_id", sa.Uuid(), sa.ForeignKey("fragrances.id", ondelete="SET NULL")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "action IN ('accepted','rejected','replaced','dismissed')", name="action_value"
        ),
    )
    op.create_index("ix_recommendation_decisions_user_id", "recommendation_decisions", ["user_id"])


def downgrade() -> None:
    op.drop_table("recommendation_decisions")
    op.drop_index("ix_wear_logs_recommendation_id", table_name="wear_logs")
    op.drop_constraint(
        "fk_wear_logs_recommendation_id_recommendations", "wear_logs", type_="foreignkey"
    )
    op.drop_column("wear_logs", "recommendation_id")
    op.drop_column("recommendation_candidates", "guidance")
    op.drop_constraint(
        op.f("ck_recommendations_evidence_coverage_range"), "recommendations", type_="check"
    )
    op.drop_constraint("wear_recommendation_inputs", "recommendations", type_="unique")
    op.drop_index("ix_recommendations_context_key", table_name="recommendations")
    op.drop_constraint(
        "fk_recommendations_calendar_event_id_calendar_events",
        "recommendations",
        type_="foreignkey",
    )
    for column in (
        "evidence_coverage",
        "score_components",
        "context_data",
        "input_fingerprint",
        "calendar_event_id",
        "context_key",
    ):
        op.drop_column("recommendations", column)
