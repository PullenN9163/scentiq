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
    ) -> None:
        self._jobs = jobs
        self._discovery = discovery
        self._layering = layering

    def get(self, user_id: UUID) -> RecommendationBundleResponse:
        input_version = self._jobs.current_input_version(user_id)
        snapshot = self._jobs.latest_snapshot(user_id)
        if snapshot is not None:
            try:
                payload = RecommendationPayload.model_validate(snapshot.payload)
            except ValidationError:
                payload = None
            if payload is not None:
                stale = snapshot.input_version != input_version
                if stale:
                    self._jobs.ensure_recommendation_job(
                        user_id,
                        input_version=input_version,
                        reason="stale_snapshot",
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
            reason="cache_miss",
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
