from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from pydantic import ValidationError

from scentiq_api.schemas import RecommendationBundleResponse, RecommendationPayload
from scentiq_api.services.discovery import DiscoveryService
from scentiq_api.services.hybrid_jobs import HybridJobService
from scentiq_api.services.layering import LayeringService


class RecommendationService:
    """Serve promoted worker snapshots, with synchronous stale-safe fallback."""

    def __init__(
        self,
        jobs: HybridJobService,
        discovery: DiscoveryService,
        layering: LayeringService,
        *,
        catalog_version: str,
        algorithm_version: str,
        max_age: timedelta,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._jobs = jobs
        self._discovery = discovery
        self._layering = layering
        self._catalog_version = catalog_version
        self._algorithm_version = algorithm_version
        self._max_age = max_age
        self._clock = clock

    def get(self, user_id: UUID) -> RecommendationBundleResponse:
        input_version = self._jobs.current_input_version(user_id)
        snapshot = self._jobs.latest_snapshot(user_id)
        if snapshot is not None:
            try:
                payload = RecommendationPayload.model_validate(snapshot.payload)
            except ValidationError:
                payload = None
            if payload is not None:
                created_at = snapshot.created_at
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=UTC)
                stale = (
                    snapshot.input_version != input_version
                    or snapshot.catalog_version != self._catalog_version
                    or snapshot.algorithm_version != self._algorithm_version
                    or self._clock() - created_at >= self._max_age
                )
                if stale:
                    self._jobs.ensure_recommendation_job(
                        user_id,
                        input_version=input_version,
                        reason="stale_snapshot",
                        force_refresh=snapshot.input_version == input_version,
                    )
                return RecommendationBundleResponse(
                    payload=payload,
                    input_version=snapshot.input_version,
                    generated_at=snapshot.created_at,
                    is_stale=stale,
                    refresh_status="pending" if stale else "fresh",
                )

        self._jobs.ensure_recommendation_job(
            user_id,
            input_version=input_version,
            reason="invalid_snapshot" if snapshot is not None else "cache_miss",
            force_refresh=snapshot is not None,
        )
        payload = RecommendationPayload(
            discovery=self._discovery.discover(user_id),
            layering={
                mode: self._layering.suggest(user_id, mode=mode)
                for mode in ("safe", "contrast", "experimental")
            },
        )
        return RecommendationBundleResponse(
            payload=payload,
            input_version=input_version,
            is_stale=True,
            refresh_status="fallback",
        )
