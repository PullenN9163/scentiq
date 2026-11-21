"""Interaction events and learned per-user taste profiles."""

import sqlalchemy as sa
from alembic import op

revision = "20261121_0009_learning"
down_revision = "20261007_0008_layer_stacks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interaction_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("subject_type", sa.String(20), nullable=False),
        sa.Column("fragrance_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("context", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_interaction_events_user_created", "interaction_events", ["user_id", "created_at"]
    )
    op.create_table(
        "user_taste_profiles",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("affinities", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("component_weights", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    # A blend candidate is anchored on one fragrance, so uniqueness must include the blend.
    op.add_column(
        "recommendation_candidates",
        sa.Column("blend_key", sa.String(100), nullable=False, server_default=""),
    )
    op.drop_constraint(
        "recommendation_candidate_fragrance", "recommendation_candidates", type_="unique"
    )
    op.create_unique_constraint(
        "recommendation_candidate_fragrance",
        "recommendation_candidates",
        ["recommendation_id", "fragrance_id", "blend_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "recommendation_candidate_fragrance", "recommendation_candidates", type_="unique"
    )
    op.create_unique_constraint(
        "recommendation_candidate_fragrance",
        "recommendation_candidates",
        ["recommendation_id", "fragrance_id"],
    )
    op.drop_column("recommendation_candidates", "blend_key")
    op.drop_table("user_taste_profiles")
    op.drop_index("ix_interaction_events_user_created", table_name="interaction_events")
    op.drop_table("interaction_events")
