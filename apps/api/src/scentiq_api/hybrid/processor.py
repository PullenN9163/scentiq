from __future__ import annotations

from itertools import combinations
from typing import Any

from scentiq_api.hybrid.contracts import HybridFragrance, RecommendationJobInput
from scentiq_api.schemas import DiscoveryResult, LayeringMode, LayeringSuggestion
from scentiq_api.services.recommendation_scoring import (
    discovery_score,
    feature_affinity,
    pair_score,
    positive_taste_overlap,
)

DISCOVERY_SNAPSHOT_LIMIT = 200


def _discovery(
    request: RecommendationJobInput, mode: str = "balance", season: str | None = None
) -> list[DiscoveryResult]:
    owned_accords = (
        set().union(*(item.accords for item in request.owned)) if request.owned else set()
    )
    owned_notes = set().union(*(item.notes for item in request.owned)) if request.owned else set()
    owned_families = {item.family for item in request.owned if item.family}
    results: list[DiscoveryResult] = []
    for candidate in request.candidates:
        if candidate.fragrance.id in request.excluded_ids:
            continue
        if mode == "seasonal" and season is not None and season not in candidate.seasons:
            continue
        taste = positive_taste_overlap(
            candidate.accords,
            set(candidate.notes),
            owned_accords,
            owned_notes,
            request.taste_features,
        )

        expansion_parts = [key not in owned_accords for key in candidate.accords]
        if candidate.family:
            expansion_parts.append(candidate.family not in owned_families)
        expansion = sum(expansion_parts) / len(expansion_parts) if expansion_parts else 0.0
        risk = 0.0
        for owned in request.owned:
            union = set(candidate.accords) | set(owned.accords)
            overlap = (
                len(set(candidate.accords) & set(owned.accords)) / len(union) if union else 0.0
            )
            risk = max(risk, overlap, candidate.similarities.get(owned.fragrance.id, 0.0))
        season_fit = max(
            (
                candidate.seasons.get(season_name, 0.0)
                for season_name in ([season] if season else candidate.seasons)
            ),
            default=0.0,
        )
        affinity = feature_affinity(
            request.taste_features,
            accords=set(candidate.accords),
            notes=set(candidate.notes),
            family=candidate.family,
        )
        score = discovery_score(
            taste,
            expansion,
            risk,
            mode=mode,
            season_fit=season_fit if mode == "seasonal" else None,
            affinity=affinity,
        )
        evidence = (
            sum(
                (
                    bool(candidate.accords),
                    bool(candidate.notes),
                    bool(candidate.seasons),
                    bool(candidate.family),
                )
            )
            / 4
        )
        reasons = [
            f"{round(taste * 100)}% match to positive taste signals; "
            "unrated ownership is weak evidence.",
            f"{round(expansion * 100)}% of recorded profile signals add collection variety.",
            f"{round(risk * 100)}% nearest-profile redundancy risk.",
        ]
        if mode == "seasonal" and season is not None:
            reasons.append(f"Recorded {season} suitability: {round(season_fit * 100)}%.")
        if affinity > 0:
            reasons.append("Personal taste fit from explicit preferences and rated scent profiles.")
        elif affinity < 0:
            reasons.append("Some recorded scent signals conflict with your personal taste.")
        if evidence < 0.5:
            reasons.append(
                "Limited catalog evidence; compare the fragrance details before deciding."
            )
        results.append(
            DiscoveryResult(
                fragrance=candidate.fragrance,
                taste_match=round(taste, 4),
                collection_expansion=round(expansion, 4),
                redundancy_risk=round(risk, 4),
                score=round(score, 4),
                generation_mode="baseline",
                profile_version=request.profile_version,
                mode=mode,
                season_fit=season_fit if mode == "seasonal" else None,
                evidence_coverage=evidence,
                reasons=reasons,
            )
        )
    return sorted(
        results,
        key=lambda result: (
            -result.score,
            -(result.fragrance.rating_count or 0),
            str(result.fragrance.id),
        ),
    )[:2000]


def _layer(
    first: HybridFragrance, second: HybridFragrance, mode: LayeringMode, features: dict[str, float]
) -> LayeringSuggestion:
    shared_notes = sorted(set(first.notes) & set(second.notes))
    complementary = sorted(set(first.accords) ^ set(second.accords))
    season_overlap = max(
        (min(weight, second.seasons.get(season, 0.0)) for season, weight in first.seasons.items()),
        default=0.0,
    )
    shared_ratio = len(shared_notes) / max(len(set(first.notes) | set(second.notes)), 1)
    contrast_ratio = len(complementary) / max(len(set(first.accords) | set(second.accords)), 1)
    affinity = (
        sum(
            feature_affinity(
                features, accords=set(item.accords), notes=set(item.notes), family=item.family
            )
            for item in (first, second)
        )
        / 2
    )
    score = pair_score(shared_ratio, contrast_ratio, season_overlap, mode, affinity)
    return LayeringSuggestion(
        first=first.fragrance,
        second=second.fragrance,
        mode=mode,
        score=round(score, 4),
        shared_notes=shared_notes,
        complementary_accords=complementary,
        season_overlap=round(season_overlap, 4),
    )


def _layering(request: RecommendationJobInput, mode: LayeringMode) -> list[LayeringSuggestion]:
    return sorted(
        (
            _layer(first, second, mode, request.taste_features)
            for first, second in combinations(request.owned, 2)
            if first.fragrance.id not in request.excluded_ids
            and second.fragrance.id not in request.excluded_ids
        ),
        key=lambda result: (-result.score, str(result.first.id), str(result.second.id)),
    )[:12]


def process_recommendation(request: RecommendationJobInput) -> dict[str, Any]:
    """Return the stable bundle envelope populated by the scoring task."""
    return {
        "profile_version": request.profile_version,
        "discovery": [item.model_dump(mode="json") for item in _discovery(request)[:25]],
        "discovery_modes": {
            mode: [
                item.model_dump(mode="json")
                for item in _discovery(request, mode)[:DISCOVERY_SNAPSHOT_LIMIT]
            ]
            for mode in ("balance", "taste", "explore")
        },
        "discovery_seasonal": {
            season: [
                item.model_dump(mode="json")
                for item in _discovery(request, "seasonal", season)[:DISCOVERY_SNAPSHOT_LIMIT]
            ]
            for season in ("spring", "summer", "fall", "winter")
        },
        "layering": {
            mode: [item.model_dump(mode="json") for item in _layering(request, mode)]
            for mode in ("safe", "contrast", "experimental")
        },
    }
