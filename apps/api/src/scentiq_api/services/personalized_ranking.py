"""Common context and bounded ranking adapter for every recommendation surface."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from scentiq_api.services.ai_ranking import RankingResult, rank_candidates
from scentiq_api.services.recommendation_context import RecommendationContextBuilder
from scentiq_api.services.taste_profile import TasteProfile


def surface_context(session: Session, user_id: UUID, profile: TasteProfile) -> dict[str, Any]:
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    context = RecommendationContextBuilder(session).build(
        user_id, now, source="today", key="context"
    )
    return {**context, "taste_features": profile.features, "variety_preference": profile.variety}


def rerank(
    session: Session,
    user_id: UUID,
    *,
    surface: str,
    candidates: list[dict[str, Any]],
    context: dict[str, Any],
    version: str,
) -> RankingResult:
    fingerprint = hashlib.sha256(
        json.dumps(
            {"context": context, "profile": version, "candidates": candidates},
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()
    return rank_candidates(
        session,
        user_id,
        candidates=candidates,
        context=context,
        fingerprint=fingerprint,
        surface=surface,
    )
