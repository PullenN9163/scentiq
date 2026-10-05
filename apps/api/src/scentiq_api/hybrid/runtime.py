from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from scentiq_api.hybrid.contracts import (
    HybridCollectionItem,
    HybridPreferences,
    JobPointer,
    PoisonMessage,
    RecommendationJobInput,
    RecommendationJobResult,
    ResultPointer,
)
from scentiq_api.hybrid.transport import HybridTransport
from scentiq_api.models import AsyncJob, UserCollectionItem, UserPreference
from scentiq_api.repositories import HybridJobRepository
from scentiq_api.services import HybridJobService

JOB_QUEUE = "hybrid-jobs"
RESULT_QUEUE = "hybrid-results"
POISON_QUEUE = "hybrid-jobs-poison"
MAX_DELIVERIES = 5


def _model_json(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")


class HybridDispatcher:
    def __init__(
        self,
        session: Session,
        transport: HybridTransport,
        *,
        catalog_version: str,
    ) -> None:
        self._session = session
        self._transport = transport
        self._catalog_version = catalog_version

    def dispatch_pending(self, *, limit: int = 25) -> int:
        jobs = list(
            self._session.scalars(
                select(AsyncJob)
                .where(AsyncJob.status == "pending")
                .order_by(AsyncJob.created_at, AsyncJob.id)
                .limit(limit)
            )
        )
        dispatched = 0
        for job in jobs:
            if job.job_type != "recommendation_bundle":
                continue
            request = self._recommendation_input(job)
            input_blob = f"hybrid/jobs/{job.id}/input.json"
            self._transport.upload_json(input_blob, _model_json(request))
            self._transport.enqueue(
                JOB_QUEUE,
                _model_json(JobPointer(job_id=job.id, input_blob=input_blob)),
            )
            job.input_blob = input_blob
            job.status = "enqueued"
            job.enqueued_at = datetime.now(UTC)
            dispatched += 1
        self._session.flush()
        return dispatched

    def _recommendation_input(self, job: AsyncJob) -> RecommendationJobInput:
        if job.user_id is None or job.input_version is None:
            raise ValueError("Recommendation job is missing member version data")
        collection = list(
            self._session.scalars(
                select(UserCollectionItem)
                .where(UserCollectionItem.user_id == job.user_id)
                .order_by(UserCollectionItem.id)
            )
        )
        preferences = self._session.get(UserPreference, job.user_id)
        return RecommendationJobInput(
            job_id=job.id,
            user_id=job.user_id,
            input_version=job.input_version,
            catalog_version=self._catalog_version,
            collection=[
                HybridCollectionItem(
                    fragrance_id=item.fragrance_id,
                    status=item.status,
                    user_rating=item.user_rating,
                )
                for item in collection
            ],
            preferences=(
                HybridPreferences(
                    preferred_season=preferences.preferred_season,
                    preferred_occasion=preferences.preferred_occasion,
                    preferred_projection=preferences.preferred_projection,
                    preferred_longevity=(
                        float(preferences.preferred_longevity)
                        if preferences.preferred_longevity is not None
                        else None
                    ),
                    maximum_sprays=preferences.maximum_sprays,
                )
                if preferences is not None
                else None
            ),
        )


class HybridWorker:
    def __init__(
        self,
        transport: HybridTransport,
        *,
        processor: Callable[[RecommendationJobInput], dict[str, Any]],
        algorithm_version: str,
    ) -> None:
        self._transport = transport
        self._processor = processor
        self._algorithm_version = algorithm_version

    def process_next(self) -> bool:
        message = self._transport.receive(JOB_QUEUE)
        if message is None:
            return False
        job_id = None
        try:
            pointer = JobPointer.model_validate_json(message.body)
            job_id = pointer.job_id
            request = RecommendationJobInput.model_validate(
                self._transport.download_json(pointer.input_blob)
            )
            if request.job_id != pointer.job_id:
                raise ValueError("Job pointer does not match input")
            self._transport.renew(JOB_QUEUE, message, visibility_timeout=300)
            result = RecommendationJobResult(
                job_id=request.job_id,
                input_version=request.input_version,
                algorithm_version=self._algorithm_version,
                catalog_version=request.catalog_version,
                payload=self._processor(request),
            )
            output_blob = f"hybrid/jobs/{request.job_id}/result.json"
            self._transport.upload_json(output_blob, _model_json(result))
            self._transport.enqueue(
                RESULT_QUEUE,
                _model_json(ResultPointer(job_id=request.job_id, output_blob=output_blob)),
            )
            self._transport.delete(JOB_QUEUE, message)
            return True
        except KeyError, ValueError, ValidationError, json.JSONDecodeError:
            if message.dequeue_count >= MAX_DELIVERIES:
                if job_id is None:
                    try:
                        job_id = JobPointer.model_validate_json(message.body).job_id
                    except ValueError, ValidationError:
                        return False
                poison = PoisonMessage(
                    job_id=job_id,
                    error_code="invalid_job_input",
                    dequeue_count=message.dequeue_count,
                )
                self._transport.enqueue(POISON_QUEUE, _model_json(poison))
                self._transport.delete(JOB_QUEUE, message)
            return False


class HybridResultApplier:
    def __init__(self, session: Session, transport: HybridTransport) -> None:
        self._session = session
        self._transport = transport

    def apply_next(self) -> bool:
        message = self._transport.receive(RESULT_QUEUE)
        if message is None:
            return False
        pointer = ResultPointer.model_validate_json(message.body)
        result = RecommendationJobResult.model_validate(
            self._transport.download_json(pointer.output_blob)
        )
        if result.job_id != pointer.job_id:
            raise ValueError("Result pointer does not match output")
        HybridJobService(HybridJobRepository(self._session)).promote_recommendation_result(
            result.job_id,
            payload=result.payload,
            algorithm_version=result.algorithm_version,
            catalog_version=result.catalog_version,
        )
        self._transport.delete(RESULT_QUEUE, message)
        self._session.flush()
        return True
