from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from scentiq_api.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin


class RecommendationState(TimestampMixin, Base):
    __tablename__ = "recommendation_states"
    __table_args__ = (CheckConstraint("input_version >= 0", name="input_version_nonnegative"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    input_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class AsyncJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "async_jobs"
    __table_args__ = (
        CheckConstraint(
            "job_type IN ('recommendation_bundle', 'catalog_import')",
            name="job_type_value",
        ),
        CheckConstraint(
            "status IN ('pending', 'enqueued', 'processing', 'succeeded', 'failed', "
            "'superseded', 'poisoned')",
            name="status_value",
        ),
        CheckConstraint("input_version IS NULL OR input_version >= 0", name="input_version_value"),
        CheckConstraint("attempt_count >= 0", name="attempt_count_nonnegative"),
        CheckConstraint("last_dequeue_count >= 0", name="last_dequeue_count_nonnegative"),
    )

    job_type: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    input_version: Mapped[int | None] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True)
    reason: Mapped[str] = mapped_column(String(80))
    schema_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    input_blob: Mapped[str | None] = mapped_column(String(512))
    output_blob: Mapped[str | None] = mapped_column(String(512))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_dequeue_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    execution_id: Mapped[str | None] = mapped_column(String(36))
    error_code: Mapped[str | None] = mapped_column(String(80))
    enqueued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RecommendationSnapshot(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "recommendation_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "recommendation_type",
            "variant_key",
            "input_version",
            name="recommendation_snapshot_version",
        ),
        CheckConstraint("input_version >= 0", name="input_version_nonnegative"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source_job_id: Mapped[UUID] = mapped_column(
        ForeignKey("async_jobs.id", ondelete="CASCADE"), unique=True
    )
    recommendation_type: Mapped[str] = mapped_column(
        String(40), default="bundle", server_default="bundle"
    )
    variant_key: Mapped[str] = mapped_column(
        String(120), default="default", server_default="default"
    )
    input_version: Mapped[int] = mapped_column(Integer)
    algorithm_version: Mapped[str] = mapped_column(String(40))
    catalog_version: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
