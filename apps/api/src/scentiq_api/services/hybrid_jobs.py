from __future__ import annotations

from typing import Any
from uuid import UUID

from scentiq_api.models import AsyncJob, RecommendationSnapshot
from scentiq_api.repositories import HybridJobRepository


class HybridJobService:
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
    ) -> AsyncJob:
        idempotency_key = f"recommendation_bundle:{user_id}:{input_version}"
        existing = self._repository.job_by_key(idempotency_key)
        if existing is not None:
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
        payload: dict[str, Any],
        algorithm_version: str,
        catalog_version: str,
    ) -> RecommendationSnapshot | None:
        job = self._repository.get_job(job_id)
        if job is None or job.user_id is None or job.input_version is None:
            return None
        existing = self._repository.snapshot_for_job(job_id)
        if existing is not None:
            return existing
        state = self._repository.state_for_update(job.user_id)
        if job.input_version != state.input_version:
            job.status = "superseded"
            return None
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
        return snapshot

    def latest_snapshot(self, user_id: UUID) -> RecommendationSnapshot | None:
        return self._repository.latest_snapshot(user_id)
