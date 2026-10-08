from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from scentiq_api.hybrid.contracts import (
    HybridCollectionItem,
    HybridFragrance,
    HybridPreferences,
    JobPointer,
    PoisonMessage,
    RecommendationJobInput,
    RecommendationJobResult,
    ResultPointer,
)
from scentiq_api.hybrid.transport import HybridQueueMessage, HybridTransport
from scentiq_api.models import AsyncJob, Fragrance, UserCollectionItem, UserPreference
from scentiq_api.repositories import DiscoveryRepository, HybridJobRepository, LayeringRepository
from scentiq_api.services import HybridJobService
from scentiq_api.services.fragrances import to_fragrance_summary

JOB_QUEUE = "hybrid-jobs"
RESULT_QUEUE = "hybrid-results"
POISON_QUEUE = "hybrid-jobs-poison"
MAX_DELIVERIES = 5


def _model_json(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")


def _hybrid_fragrance(
    item: Fragrance,
    *,
    similarities: dict[tuple[Any, Any], float] | None = None,
    owned_ids: set[Any] | None = None,
    include_seasons: bool = True,
) -> HybridFragrance:
    similarity_map = {
        owned_id: strength
        for owned_id in (owned_ids or set())
        if (strength := (similarities or {}).get((item.id, owned_id))) is not None
    }
    return HybridFragrance(
        fragrance=to_fragrance_summary(item),
        accords={link.accord.slug: float(link.weight) for link in item.accord_links},
        notes={link.note.slug: float(link.weight or 0.5) for link in item.note_links},
        seasons=(
            {link.season: float(link.weight) for link in item.seasons} if include_seasons else {}
        ),
        family=item.olfactory_family,
        similarities=similarity_map,
    )


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
            if job.execution_id is None:
                job.execution_id = str(uuid4())
            request = self._recommendation_input(job)
            input_blob = f"hybrid/jobs/{job.id}/{job.execution_id}/input.json"
            self._transport.upload_json(input_blob, _model_json(request))
            self._transport.enqueue(
                JOB_QUEUE,
                _model_json(
                    JobPointer(
                        job_id=job.id,
                        execution_id=job.execution_id,
                        input_blob=input_blob,
                    )
                ),
            )
            job.input_blob = input_blob
            job.status = "enqueued"
            job.enqueued_at = datetime.now(UTC)
            dispatched += 1
        self._session.flush()
        return dispatched

    def _recommendation_input(self, job: AsyncJob) -> RecommendationJobInput:
        if job.user_id is None or job.input_version is None or job.execution_id is None:
            raise ValueError("Recommendation job is missing member version data")
        collection = list(
            self._session.scalars(
                select(UserCollectionItem)
                .where(UserCollectionItem.user_id == job.user_id)
                .order_by(UserCollectionItem.id)
            )
        )
        preferences = self._session.get(UserPreference, job.user_id)
        discovery_repository = DiscoveryRepository(self._session)
        owned = LayeringRepository(self._session).owned(job.user_id)
        candidates = discovery_repository.candidates(job.user_id)
        owned_ids = {item.id for item in owned}
        similarities = discovery_repository.similarity_strengths(
            {item.id for item in candidates}, owned_ids
        )
        return RecommendationJobInput(
            job_id=job.id,
            execution_id=job.execution_id,
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
            owned=[_hybrid_fragrance(item) for item in owned],
            candidates=[
                _hybrid_fragrance(
                    item,
                    similarities=similarities,
                    owned_ids=owned_ids,
                    include_seasons=False,
                )
                for item in candidates
            ],
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

    def _handle_failure(
        self,
        message: HybridQueueMessage,
        job_id: UUID | None,
        execution_id: UUID | None,
        *,
        error_code: str,
    ) -> bool:
        if message.dequeue_count < MAX_DELIVERIES:
            return False
        if job_id is None:
            try:
                pointer = JobPointer.model_validate_json(message.body)
                job_id = pointer.job_id
                execution_id = pointer.execution_id
            except ValueError, ValidationError:
                self._transport.delete(JOB_QUEUE, message)
                return False
        poison = PoisonMessage(
            job_id=job_id,
            execution_id=execution_id,
            error_code=error_code,
            dequeue_count=message.dequeue_count,
        )
        self._transport.enqueue(POISON_QUEUE, _model_json(poison))
        self._transport.delete(JOB_QUEUE, message)
        return False

    def process_next(self) -> bool:
        message = self._transport.receive(JOB_QUEUE)
        if message is None:
            return False
        job_id = None
        execution_id = None
        try:
            pointer = JobPointer.model_validate_json(message.body)
            job_id = pointer.job_id
            execution_id = pointer.execution_id
            request = RecommendationJobInput.model_validate(
                self._transport.download_json(pointer.input_blob)
            )
            if request.job_id != pointer.job_id or (
                pointer.execution_id is not None and request.execution_id != pointer.execution_id
            ):
                raise ValueError("Job pointer does not match input")
            self._transport.renew(JOB_QUEUE, message, visibility_timeout=300)
            result = RecommendationJobResult(
                job_id=request.job_id,
                execution_id=request.execution_id,
                input_version=request.input_version,
                algorithm_version=self._algorithm_version,
                catalog_version=request.catalog_version,
                payload=self._processor(request),
            )
            output_blob = f"hybrid/jobs/{request.job_id}/{request.execution_id}/result.json"
            self._transport.upload_json(output_blob, _model_json(result))
            self._transport.enqueue(
                RESULT_QUEUE,
                _model_json(
                    ResultPointer(
                        job_id=request.job_id,
                        execution_id=request.execution_id,
                        output_blob=output_blob,
                    )
                ),
            )
            self._transport.delete(JOB_QUEUE, message)
            return True
        except KeyError, ValueError, ValidationError, json.JSONDecodeError:
            return self._handle_failure(
                message, job_id, execution_id, error_code="invalid_job_input"
            )
        except Exception:
            return self._handle_failure(
                message, job_id, execution_id, error_code="processing_failed"
            )


class HybridResultApplier:
    def __init__(self, session: Session, transport: HybridTransport) -> None:
        self._session = session
        self._transport = transport

    def apply_next(self) -> bool:
        message = self._transport.receive(RESULT_QUEUE)
        if message is None:
            return False
        job_id: UUID | None = None
        execution_id: UUID | None = None
        try:
            pointer = ResultPointer.model_validate_json(message.body)
            job_id = pointer.job_id
            execution_id = pointer.execution_id
            result = RecommendationJobResult.model_validate(
                self._transport.download_json(pointer.output_blob)
            )
            if result.job_id != pointer.job_id or (
                pointer.execution_id is not None and result.execution_id != pointer.execution_id
            ):
                raise ValueError("Result pointer does not match output")
            HybridJobService(HybridJobRepository(self._session)).promote_recommendation_result(
                result.job_id,
                execution_id=result.execution_id,
                payload=result.payload,
                algorithm_version=result.algorithm_version,
                catalog_version=result.catalog_version,
            )
            # Commit the idempotent promotion before acknowledging the queue item.
            # If acknowledgement fails, redelivery safely observes the same snapshot.
            self._session.commit()
            self._transport.delete(RESULT_QUEUE, message)
            return True
        except KeyError, ValueError, ValidationError, json.JSONDecodeError:
            if message.dequeue_count < MAX_DELIVERIES:
                return False
            if job_id is None:
                try:
                    pointer = ResultPointer.model_validate_json(message.body)
                    job_id = pointer.job_id
                    execution_id = pointer.execution_id
                except ValueError, ValidationError:
                    self._transport.delete(RESULT_QUEUE, message)
                    return False
            self._transport.enqueue(
                POISON_QUEUE,
                _model_json(
                    PoisonMessage(
                        job_id=job_id,
                        execution_id=execution_id,
                        error_code="invalid_job_result",
                        dequeue_count=message.dequeue_count,
                    )
                ),
            )
            self._transport.delete(RESULT_QUEUE, message)
            return False


class HybridPoisonApplier:
    def __init__(self, session: Session, transport: HybridTransport) -> None:
        self._session = session
        self._transport = transport

    def apply_next(self) -> bool:
        message = self._transport.receive(POISON_QUEUE)
        if message is None:
            return False
        try:
            poison = PoisonMessage.model_validate_json(message.body)
        except ValidationError, ValueError:
            if message.dequeue_count >= MAX_DELIVERIES:
                self._transport.delete(POISON_QUEUE, message)
            return False
        HybridJobService(HybridJobRepository(self._session)).mark_poisoned(
            poison.job_id,
            execution_id=poison.execution_id,
            error_code=poison.error_code,
            dequeue_count=poison.dequeue_count,
        )
        self._session.commit()
        self._transport.delete(POISON_QUEUE, message)
        return True
