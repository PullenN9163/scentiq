from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from scentiq_api.models import AsyncJob, RecommendationSnapshot, RecommendationState


class HybridJobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def state_for_update(self, user_id: UUID) -> RecommendationState:
        state = self._session.get(RecommendationState, user_id)
        if state is None:
            state = RecommendationState(user_id=user_id, input_version=0)
            self._session.add(state)
            self._session.flush()
        return state

    def job_by_key(self, idempotency_key: str) -> AsyncJob | None:
        return self._session.scalar(
            select(AsyncJob).where(AsyncJob.idempotency_key == idempotency_key)
        )

    def add_job(self, job: AsyncJob) -> AsyncJob:
        self._session.add(job)
        self._session.flush()
        return job

    def get_job(self, job_id: UUID) -> AsyncJob | None:
        return self._session.get(AsyncJob, job_id)

    def add_snapshot(self, snapshot: RecommendationSnapshot) -> RecommendationSnapshot:
        self._session.add(snapshot)
        self._session.flush()
        return snapshot

    def latest_snapshot(self, user_id: UUID) -> RecommendationSnapshot | None:
        return self._session.scalar(
            select(RecommendationSnapshot)
            .where(RecommendationSnapshot.user_id == user_id)
            .order_by(
                RecommendationSnapshot.input_version.desc(),
                RecommendationSnapshot.created_at.desc(),
            )
            .limit(1)
        )
