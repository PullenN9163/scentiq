from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from scentiq_api.auth import AuthenticatedUser, CurrentUserDependency
from scentiq_api.models import Fragrance
from scentiq_api.repositories import DiscoveryRepository, HybridJobRepository
from scentiq_api.schemas.discovery import DiscoveryFeedResponse, DiscoveryMode, DiscoveryResult
from scentiq_api.services import DiscoveryService, HybridJobService
from scentiq_api.services.taste_profile import TasteProfileService


def _snapshot_rows(
    payload: dict[str, object], mode: DiscoveryMode, selected_season: str | None
) -> list[DiscoveryResult]:
    try:
        if mode == "seasonal":
            variants = payload.get("discovery_seasonal")
            rows = (
                variants.get(selected_season, [])
                if isinstance(variants, dict) and selected_season
                else []
            )
        elif mode == "balance":
            variants = payload.get("discovery_modes")
            rows = (
                variants.get("balance", payload.get("discovery", []))
                if isinstance(variants, dict)
                else payload.get("discovery", [])
            )
        else:
            variants = payload.get("discovery_modes")
            rows = variants.get(mode, []) if isinstance(variants, dict) else []
        return [DiscoveryResult.model_validate(row) for row in rows]
    except ValidationError, AttributeError, TypeError:
        return []


def _snapshot_profile_metadata(
    payload: dict[str, object],
) -> tuple[str, set[UUID]] | None:
    """Return validated worker metadata suitable for a fresh feed snapshot."""
    version = payload.get("profile_version")
    excluded = payload.get("excluded_ids")
    if (
        not isinstance(version, str)
        or len(version) != 64
        or any(character not in "0123456789abcdef" for character in version.lower())
        or not isinstance(excluded, list)
    ):
        return None
    try:
        excluded_ids = {
            value if isinstance(value, UUID) else UUID(str(value)) for value in excluded
        }
    except ValueError, TypeError, AttributeError:
        return None
    return version, excluded_ids


def _safe_snapshot_page(
    rows: list[DiscoveryResult],
    *,
    owned_ids: set[UUID],
    excluded_ids: set[UUID],
    shared_ids: set[UUID],
    offset: int,
    limit: int,
) -> list[DiscoveryResult] | None:
    current = [
        item
        for item in rows
        if item.fragrance.id in shared_ids
        and item.fragrance.id not in owned_ids
        and item.fragrance.id not in excluded_ids
    ]
    if len(current) < offset + limit:
        return None
    return current[offset : offset + limit]


def create_discovery_feed_router(
    get_session: object,
    current_user: CurrentUserDependency,
    *,
    catalog_version: str,
    algorithm_version: str,
    max_age_seconds: int,
) -> APIRouter:
    router = APIRouter(tags=["discover"])

    @router.get("/discovery-feed", response_model=DiscoveryFeedResponse)
    def discovery_feed(
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
        limit: Annotated[int, Query(ge=1, le=50)] = 25,
        offset: Annotated[int, Query(ge=0)] = 0,
        gender: Literal["male", "female", "unisex"] | None = None,
        family: Annotated[str | None, Query(max_length=60)] = None,
        season: Literal["spring", "summer", "fall", "winter"] | None = None,
        accord: Annotated[str | None, Query(max_length=100)] = None,
        minimum_value: Annotated[float | None, Query(ge=1, le=5)] = None,
        mode: DiscoveryMode = "balance",
    ) -> DiscoveryFeedResponse:
        user_id = user.user_id
        jobs = HybridJobService(HybridJobRepository(session))
        input_version = jobs.current_input_version(user_id)
        snapshot = jobs.latest_snapshot(user_id)
        filtered = any(
            value is not None for value in (gender, family, season, accord, minimum_value)
        )
        profile = None
        results: list[DiscoveryResult] | None = None
        generated_at = None
        stale = True
        refresh_required = snapshot is None
        payload: dict[str, object] = {}
        compatible_profile = False
        hard_versions_match = False
        trusted_excluded_ids: set[UUID] | None = None
        if snapshot is not None:
            payload = snapshot.payload if isinstance(snapshot.payload, dict) else {}
            hard_versions_match = (
                snapshot.catalog_version == catalog_version
                and snapshot.algorithm_version == algorithm_version
            )
            snapshot_time = snapshot.created_at
            if snapshot_time.tzinfo is None:
                snapshot_time = snapshot_time.replace(tzinfo=UTC)
            stale = (
                snapshot.input_version != input_version
                or not hard_versions_match
                or datetime.now(UTC) - snapshot_time >= timedelta(seconds=max_age_seconds)
            )
            refresh_required = stale
            metadata = _snapshot_profile_metadata(payload)
            if (
                not filtered
                and mode != "seasonal"
                and snapshot.input_version == input_version
                and hard_versions_match
                and not stale
                and metadata is not None
            ):
                _, trusted_excluded_ids = metadata
                compatible_profile = True
            else:
                profile = TasteProfileService(session).for_user(user_id)
                compatible_profile = payload.get("profile_version") == profile.version or (
                    payload.get("profile_version") is None
                    and not profile.features
                    and not profile.excluded_ids
                )
            stale = stale or not compatible_profile
            refresh_required = stale
        else:
            profile = TasteProfileService(session).for_user(user_id)
        if snapshot is not None and not filtered:
            selected_season = None
            if mode == "seasonal":
                from scentiq_api.services.personalized_ranking import surface_context

                assert profile is not None
                context = surface_context(session, user_id, profile)
                selected_season = str(context.get("season", "spring"))
            variants = payload.get(
                "discovery_seasonal" if mode == "seasonal" else "discovery_modes"
            )
            if mode == "seasonal":
                mode_available = isinstance(variants, dict) and selected_season in variants
            elif mode == "balance":
                mode_available = (
                    isinstance(variants, dict) and "balance" in variants
                ) or isinstance(payload.get("discovery"), list)
            else:
                mode_available = isinstance(variants, dict) and mode in variants
            if not mode_available:
                refresh_required = True
                stale = True
            parsed = _snapshot_rows(payload, mode, selected_season)
            if compatible_profile and hard_versions_match:
                owned_ids = {item.id for item in DiscoveryRepository(session).owned(user_id)}
                candidate_ids = {item.fragrance.id for item in parsed}
                shared_ids = (
                    set(
                        session.scalars(
                            select(Fragrance.id).where(
                                Fragrance.id.in_(candidate_ids),
                                Fragrance.owner_user_id.is_(None),
                            )
                        )
                    )
                    if candidate_ids
                    else set()
                )
                page = _safe_snapshot_page(
                    parsed,
                    owned_ids=owned_ids,
                    excluded_ids=trusted_excluded_ids
                    if trusted_excluded_ids is not None
                    else set(profile.excluded_ids if profile is not None else ()),
                    shared_ids=shared_ids,
                    offset=offset,
                    limit=limit,
                )
                if page is not None:
                    latest_input_version = jobs.current_input_version(user_id)
                    if latest_input_version != input_version:
                        # A taste-affecting write committed while the snapshot
                        # page was being checked. Drop it and recompute against
                        # the newly observed version.
                        input_version = latest_input_version
                        stale = True
                        refresh_required = True
                        page = None
                generated_at = snapshot.created_at
                results = page
        if results is None:
            if refresh_required:
                jobs.ensure_recommendation_job(
                    user_id,
                    input_version=input_version,
                    reason="invalid_snapshot" if snapshot is not None else "cache_miss",
                    force_refresh=snapshot is not None and snapshot.input_version == input_version,
                )
            results = DiscoveryService(DiscoveryRepository(session)).discover(
                user_id,
                limit=limit,
                offset=offset,
                gender=gender,
                family=family,
                season=season,
                accord=accord,
                minimum_value=minimum_value,
                mode=mode,
                rank_with_ai=False,
            )
            session.commit()
            return DiscoveryFeedResponse(
                items=results,
                mode=mode,
                limit=limit,
                offset=offset,
                refresh_status="fallback",
            )
        if stale and results is not None:
            jobs.ensure_recommendation_job(
                user_id,
                input_version=input_version,
                reason="stale_snapshot",
                force_refresh=snapshot is not None and snapshot.input_version == input_version,
            )
            session.commit()
        return DiscoveryFeedResponse(
            items=results,
            mode=mode,
            limit=limit,
            offset=offset,
            generated_at=generated_at,
            refresh_status="pending" if stale else "fresh",
        )

    return router
