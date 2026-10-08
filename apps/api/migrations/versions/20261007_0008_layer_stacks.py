"""Normalize saved layering combinations and retain legacy pair wear history."""

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "20261007_0008_layer_stacks"
down_revision = "20261007_0007_wear_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "layer_stacks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("goal", sa.String(30)),
        sa.Column("notes", sa.Text()),
        sa.Column("score_snapshot", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("evidence_coverage", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column(
            "algorithm_version", sa.String(40), nullable=False, server_default="legacy-pair-v1"
        ),
        sa.Column("score_components", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_layer_stacks_user_id", "layer_stacks", ["user_id"])
    op.create_table(
        "layer_stack_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "stack_id",
            sa.Uuid(),
            sa.ForeignKey("layer_stacks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "fragrance_id",
            sa.Uuid(),
            sa.ForeignKey("fragrances.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("suggested_sprays", sa.Integer(), nullable=False),
        sa.UniqueConstraint("stack_id", "fragrance_id", name="layer_stack_fragrance"),
        sa.UniqueConstraint("stack_id", "position", name="layer_stack_position"),
        sa.CheckConstraint("position BETWEEN 1 AND 3", name="position_range"),
        sa.CheckConstraint("suggested_sprays BETWEEN 1 AND 6", name="sprays_range"),
        sa.CheckConstraint("role IN ('anchor', 'bridge', 'accent')", name="role_value"),
    )
    op.create_index("ix_layer_stack_items_stack_id", "layer_stack_items", ["stack_id"])
    op.create_table(
        "layer_stack_wears",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "stack_id",
            sa.Uuid(),
            sa.ForeignKey("layer_stacks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("worn_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rating", sa.Integer()),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="rating_range"),
    )
    op.create_index("ix_layer_stack_wears_stack_id", "layer_stack_wears", ["stack_id"])
    op.create_index("ix_layer_stack_wears_user_id", "layer_stack_wears", ["user_id"])
    op.create_index("ix_layer_stack_wears_worn_at", "layer_stack_wears", ["worn_at"])
    # Preserve every legacy wear/rating/note. Original rows remain for old consumers.
    bind = op.get_bind()
    metadata = sa.MetaData()
    stacks = sa.Table("layer_stacks", metadata, autoload_with=bind)
    items = sa.Table("layer_stack_items", metadata, autoload_with=bind)
    wears = sa.Table("layer_stack_wears", metadata, autoload_with=bind)
    legacy = sa.Table("layering_logs", metadata, autoload_with=bind)
    for row in bind.execute(sa.select(legacy)).mappings():
        stack_id = uuid4()
        bind.execute(
            stacks.insert().values(
                id=stack_id,
                user_id=row["user_id"],
                name="Saved pairing",
                mode="balanced",
                notes=row["notes"],
                created_at=row["created_at"],
                updated_at=row["created_at"],
            )
        )
        bind.execute(
            items.insert(),
            [
                dict(
                    id=uuid4(),
                    stack_id=stack_id,
                    fragrance_id=row["primary_fragrance_id"],
                    position=1,
                    role="anchor",
                    suggested_sprays=2,
                ),
                dict(
                    id=uuid4(),
                    stack_id=stack_id,
                    fragrance_id=row["secondary_fragrance_id"],
                    position=2,
                    role="accent",
                    suggested_sprays=1,
                ),
            ],
        )
        bind.execute(
            wears.insert().values(
                id=uuid4(),
                stack_id=stack_id,
                user_id=row["user_id"],
                worn_at=row["worn_at"],
                rating=row["rating"],
                notes=row["notes"],
                created_at=row["created_at"],
            )
        )


def downgrade() -> None:
    op.drop_table("layer_stack_wears")
    op.drop_table("layer_stack_items")
    op.drop_table("layer_stacks")
