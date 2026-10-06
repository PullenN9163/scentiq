from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from scentiq_api.models import AsyncJob, RecommendationSnapshot
from scentiq_api.repositories import HybridJobRepository


class HybridJobService:
    MAX_JOB_ATTEMPTS = 3

    def __init__(self, repository: HybridJobRepository) -> None:
        self._repository = repository

    def invalidate_recommendations(self, user_id: UUID, *, reason: str) -> AsyncJob:
        state = self._repository.state_for_update(user_id)
        state.input_version += 1
        return self.ensure_recommendation_job(
            user_id,
            input_version=state.input_version,
            reason=reason,
        )

    def ensure_recommendation_job(
        self,
        user_id: UUID,
        *,
        input_version: int,
        reason: str,
        force_refresh: bool = False,
    ) -> AsyncJob:
        idempotency_key = f"recommendation_bundle:{user_id}:{input_version}"
        existing = self._repository.job_by_key(idempotency_key)
        if existing is not None:
            retryable_terminal = (
                existing.status in {"failed", "poisoned"}
                and existing.attempt_count < self.MAX_JOB_ATTEMPTS
            )
            refreshable_success = force_refresh and existing.status == "succeeded"
            if retryable_terminal or refreshable_success:
                existing.status = "pending"
                existing.reason = reason
                existing.error_code = None
                existing.input_blob = None
                existing.output_blob = None
                # Reserve the next execution identity immediately so delayed
                # messages from the previous execution fail closed even while
                # this job is waiting in the pending backlog.
                existing.execution_id = str(uuid4())
                existing.enqueued_at = None
                existing.started_at = None
                existing.finished_at = None
            return existing
        return self._repository.add_job(
            AsyncJob(
                job_type="recommendation_bundle",
                status="pending",
                user_id=user_id,
                input_version=input_version,
                idempotency_key=idempotency_key,
                reason=reason,
                schema_version=1,
                attempt_count=0,
            )
        )

    def promote_recommendation_result(
        self,
        job_id: UUID,
        *,
        execution_id: UUID | None = None,
        payload: dict[str, Any],
        algorithm_version: str,
        catalog_version: str,
    ) -> RecommendationSnapshot | None:
        job = self._repository.get_job(job_id)
        if job is None or job.user_id is None or job.input_version is None:
            return None
        normalized_execution_id = str(execution_id) if execution_id is not None else None
        if normalized_execution_id != job.execution_id:
            return None
        existing = self._repository.snapshot_for_job(job_id)
        state = self._repository.state_for_update(job.user_id)
        if job.input_version != state.input_version:
            job.status = "superseded"
            return None
        if existing is not None:
            existing.payload = payload
            existing.algorithm_version = algorithm_version
            existing.catalog_version = catalog_version
            existing.created_at = datetime.now(UTC)
            job.status = "succeeded"
            job.finished_at = datetime.now(UTC)
            return existing
        snapshot = self._repository.add_snapshot(
            RecommendationSnapshot(
                user_id=job.user_id,
                source_job_id=job.id,
                recommendation_type="bundle",
                variant_key="default",
                input_version=job.input_version,
                algorithm_version=algorithm_version,
                catalog_version=catalog_version,
                payload=payload,
            )
        )
        job.status = "succeeded"
        job.finished_at = datetime.now(UTC)
        return snapshot

    def mark_poisoned(
        self,
        job_id: UUID,
        *,
        execution_id: UUID | None,
        error_code: str,
        dequeue_count: int,
    ) -> AsyncJob | None:
        job = self._repository.get_job(job_id)
        if (
            job is None
            or job.status in {"succeeded", "superseded"}
            or (str(execution_id) if execution_id is not None else None) != job.execution_id
        ):
            return None
        if job.status == "poisoned":
            return job
        job.status = "poisoned"
        job.error_code = error_code
        job.attempt_count += 1
        job.last_dequeue_count = max(job.last_dequeue_count, dequeue_count)
        job.finished_at = datetime.now(UTC)
        return job

    def latest_snapshot(self, user_id: UUID) -> RecommendationSnapshot | None:
        return self._repository.latest_snapshot(user_id)

    def current_input_version(self, user_id: UUID) -> int:
        return self._repository.current_input_version(user_id)
