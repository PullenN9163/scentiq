"""Implicit interaction events that refine derived taste."""

import sqlalchemy as sa
from alembic import op

revision = "20261121_0017"
down_revision = "20261115_0016"
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
        sa.Column("fragrance_ids", sa.JSON(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_interaction_events_user_created", "interaction_events", ["user_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_interaction_events_user_created", table_name="interaction_events")
    op.drop_table("interaction_events")
