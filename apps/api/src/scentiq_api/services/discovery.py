from __future__ import annotations

from uuid import UUID

from scentiq_api.models import Fragrance
from scentiq_api.repositories import DiscoveryRepository
from scentiq_api.schemas import DiscoveryResult
from scentiq_api.schemas.discovery import DiscoveryMode
from scentiq_api.services.fragrances import to_fragrance_summary
from scentiq_api.services.personalized_ranking import rerank, surface_context
from scentiq_api.services.recommendation_scoring import discovery_score, positive_taste_overlap
from scentiq_api.services.taste_profile import TasteProfileService


def _accords(item: Fragrance) -> dict[str, float]:
    return {link.accord.slug: float(link.weight) for link in item.accord_links}


def _notes(item: Fragrance) -> set[str]:
    return {link.note.slug for link in item.note_links}


class DiscoveryService:
    """Score unowned shared fragrances with a deterministic, inspectable formula.

    Taste match is the mean of candidate accord-weight and note overlap with the
    owned collection. Collection expansion is the share of candidate accords
    plus its family that are new. Redundancy risk is the maximum of direct
    source similarity and accord Jaccard overlap with any owned fragrance. The
    final score is `0.55*taste + 0.35*expansion - 0.25*redundancy`.
    Detailed scoring runs over a bounded, popularity-ranked candidate pool so
    request cost does not grow with the full catalog.
    """

    def __init__(self, repository: DiscoveryRepository) -> None:
        self._repository = repository

    def discover(
        self,
        user_id: UUID,
        *,
        limit: int = 25,
        offset: int = 0,
        gender: str | None = None,
        family: str | None = None,
        season: str | None = None,
        accord: str | None = None,
        minimum_value: float | None = None,
        mode: DiscoveryMode = "balance",
    ) -> list[DiscoveryResult]:
        owned = self._repository.owned(user_id)
        profile = TasteProfileService(self._repository._session).for_user(user_id)
        context = surface_context(self._repository._session, user_id, profile)
        if mode == "seasonal" and season is None:
            season = str(context["season"])
        candidates = self._repository.candidates(
            user_id,
            gender=gender,
            family=family,
            season=season,
            accord=accord,
            minimum_value=minimum_value,
        )
        owned_accords = set().union(*(_accords(item) for item in owned)) if owned else set()
        owned_notes = set().union(*(_notes(item) for item in owned)) if owned else set()
        owned_families = {item.olfactory_family for item in owned if item.olfactory_family}
        similarities = self._repository.similarity_strengths(
            {item.id for item in candidates}, {item.id for item in owned}
        )

        results: list[DiscoveryResult] = []
        for candidate in candidates:
            if candidate.id in profile.excluded_ids:
                continue
            candidate_accords = _accords(candidate)
            candidate_notes = _notes(candidate)
            taste = positive_taste_overlap(
                candidate_accords, candidate_notes, owned_accords, owned_notes, profile.features
            )

            expansion_parts = [key not in owned_accords for key in candidate_accords]
            if candidate.olfactory_family:
                expansion_parts.append(candidate.olfactory_family not in owned_families)
            expansion = sum(expansion_parts) / len(expansion_parts) if expansion_parts else 0.0

            risk = 0.0
            for owned_item in owned:
                owned_item_accords = set(_accords(owned_item))
                union = set(candidate_accords) | owned_item_accords
                overlap = (
                    len(set(candidate_accords) & owned_item_accords) / len(union) if union else 0
                )
                risk = max(risk, overlap, similarities.get((candidate.id, owned_item.id), 0.0))
            season_fit = (
                max(
                    (float(link.weight) for link in candidate.seasons if link.season == season),
                    default=0.0,
                )
                if season
                else None
            )
            score = discovery_score(
                taste,
                expansion,
                risk,
                mode=mode,
                season_fit=season_fit,
                affinity=profile.affinity(candidate),
            )
            evidence = (
                sum(
                    (
                        bool(candidate_accords),
                        bool(candidate_notes),
                        bool(candidate.seasons),
                        bool(candidate.olfactory_family),
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
            if season_fit is not None:
                reasons.append(f"Recorded {season} suitability: {round(season_fit * 100)}%.")
            if profile.affinity(candidate) > 0:
                reasons.append(
                    "Personal taste fit from explicit preferences and rated scent profiles."
                )
            elif profile.affinity(candidate) < 0:
                reasons.append("Some recorded scent signals conflict with your personal taste.")
            if evidence < 0.5:
                reasons.append(
                    "Limited catalog evidence; compare the fragrance details before deciding."
                )
            results.append(
                DiscoveryResult(
                    fragrance=to_fragrance_summary(candidate),
                    taste_match=round(taste, 4),
                    collection_expansion=round(expansion, 4),
                    redundancy_risk=round(risk, 4),
                    score=round(score, 4),
                    mode=mode,
                    season_fit=season_fit,
                    evidence_coverage=evidence,
                    reasons=reasons,
                )
            )
        ranked = sorted(
            results,
            key=lambda result: (
                -result.score,
                -(result.fragrance.rating_count or 0),
                str(result.fragrance.id),
            ),
        )
        ranking = rerank(
            self._repository._session,
            user_id,
            surface="discovery",
            candidates=[
                {
                    "candidate_id": str(row.fragrance.id),
                    "baseline_score": row.score,
                    "evidence": {
                        "taste_match": row.taste_match,
                        "collection_expansion": row.collection_expansion,
                        "redundancy": row.redundancy_risk,
                        "reasons": row.reasons,
                    },
                }
                for row in ranked
            ],
            context={**context, "mode": mode, "season": season},
            version=profile.version,
        )
        by_id = {str(row.fragrance.id): row for row in ranked}
        ranked = [
            by_id[key].model_copy(
                update={
                    "generation_mode": ranking.generation_mode,
                    "profile_version": profile.version,
                    "model_version": ranking.model_version,
                    "ai_reasons": ranking.explanations.get(key, []),
                }
            )
            for key in ranking.ordered_ids
        ]
        return ranked[offset : offset + limit]
