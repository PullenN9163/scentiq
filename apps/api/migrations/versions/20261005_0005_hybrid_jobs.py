"""Add durable hybrid jobs and recommendation snapshots.

Revision ID: 20261005_0005
Revises: 20260925_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261005_0005"
down_revision: str | Sequence[str] | None = "20260925_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recommendation_states",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("input_version", sa.Integer(), server_default="0", nullable=False),
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
        sa.CheckConstraint(
            "input_version >= 0",
            name=op.f("ck_recommendation_states_input_version_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_recommendation_states_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_recommendation_states")),
    )
    op.create_table(
        "async_jobs",
        sa.Column("job_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("input_version", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.String(length=80), nullable=False),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("input_blob", sa.String(length=512), nullable=True),
        sa.Column("output_blob", sa.String(length=512), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint(
            "job_type IN ('recommendation_bundle', 'catalog_import')",
            name=op.f("ck_async_jobs_job_type_value"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'enqueued', 'processing', 'succeeded', 'failed', "
            "'superseded', 'poisoned')",
            name=op.f("ck_async_jobs_status_value"),
        ),
        sa.CheckConstraint(
            "input_version IS NULL OR input_version >= 0",
            name=op.f("ck_async_jobs_input_version_value"),
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name=op.f("ck_async_jobs_attempt_count_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_async_jobs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_async_jobs")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_async_jobs_idempotency_key")),
    )
    op.create_index(op.f("ix_async_jobs_job_type"), "async_jobs", ["job_type"])
    op.create_index(op.f("ix_async_jobs_user_id"), "async_jobs", ["user_id"])
    op.create_table(
        "recommendation_snapshots",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_job_id", sa.Uuid(), nullable=False),
        sa.Column(
            "recommendation_type", sa.String(length=40), server_default="bundle", nullable=False
        ),
        sa.Column("variant_key", sa.String(length=120), server_default="default", nullable=False),
        sa.Column("input_version", sa.Integer(), nullable=False),
        sa.Column("algorithm_version", sa.String(length=40), nullable=False),
        sa.Column("catalog_version", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "input_version >= 0",
            name=op.f("ck_recommendation_snapshots_input_version_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["source_job_id"],
            ["async_jobs.id"],
            name=op.f("fk_recommendation_snapshots_source_job_id_async_jobs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_recommendation_snapshots_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recommendation_snapshots")),
        sa.UniqueConstraint(
            "source_job_id", name=op.f("uq_recommendation_snapshots_source_job_id")
        ),
        sa.UniqueConstraint(
            "user_id",
            "recommendation_type",
            "variant_key",
            "input_version",
            name="recommendation_snapshot_version",
        ),
    )
    op.create_index(
        op.f("ix_recommendation_snapshots_user_id"),
        "recommendation_snapshots",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_recommendation_snapshots_user_id"),
        table_name="recommendation_snapshots",
    )
    op.drop_table("recommendation_snapshots")
    op.drop_index(op.f("ix_async_jobs_user_id"), table_name="async_jobs")
    op.drop_index(op.f("ix_async_jobs_job_type"), table_name="async_jobs")
    op.drop_table("async_jobs")
    op.drop_table("recommendation_states")
