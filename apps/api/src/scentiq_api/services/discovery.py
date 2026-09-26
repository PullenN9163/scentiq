from __future__ import annotations

from uuid import UUID

from scentiq_api.models import Fragrance
from scentiq_api.repositories import DiscoveryRepository
from scentiq_api.schemas import DiscoveryResult
from scentiq_api.services.fragrances import to_fragrance_summary


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
    ) -> list[DiscoveryResult]:
        owned = self._repository.owned(user_id)
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
            candidate_accords = _accords(candidate)
            candidate_notes = _notes(candidate)
            accord_total = sum(candidate_accords.values()) or 1.0
            accord_overlap = (
                sum(weight for key, weight in candidate_accords.items() if key in owned_accords)
                / accord_total
            )
            note_overlap = (
                len(candidate_notes & owned_notes) / len(candidate_notes)
                if candidate_notes
                else 0.0
            )
            taste = (accord_overlap + note_overlap) / 2

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
            score = 0.55 * taste + 0.35 * expansion - 0.25 * risk
            results.append(
                DiscoveryResult(
                    fragrance=to_fragrance_summary(candidate),
                    taste_match=round(taste, 4),
                    collection_expansion=round(expansion, 4),
                    redundancy_risk=round(risk, 4),
                    score=round(score, 4),
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
        return ranked[offset : offset + limit]
