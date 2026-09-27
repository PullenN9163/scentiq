from __future__ import annotations

from itertools import combinations
from uuid import UUID

from scentiq_api.models import Fragrance
from scentiq_api.repositories import LayeringRepository
from scentiq_api.schemas import LayeringMode, LayeringSuggestion
from scentiq_api.services.fragrances import to_fragrance_summary


def _weighted_keys(item: Fragrance, relationship: str) -> dict[str, float]:
    links = getattr(item, relationship)
    if relationship == "accord_links":
        return {link.accord.slug: float(link.weight) for link in links}
    return {link.note.slug: float(link.weight or 0.5) for link in links}


class LayeringService:
    """Rank owned pairs deterministically for safe, contrast, or experimental use.

    Safe emphasizes shared notes and season agreement; Contrast emphasizes
    non-overlapping accords while retaining some season agreement; Experimental
    emphasizes novelty. No chemistry or safety claim is made.
    """

    def __init__(self, repository: LayeringRepository) -> None:
        self._repository = repository

    def suggest(
        self,
        user_id: UUID,
        *,
        mode: LayeringMode = "safe",
        limit: int = 12,
        first_id: UUID | None = None,
        second_id: UUID | None = None,
    ) -> list[LayeringSuggestion]:
        results: list[LayeringSuggestion] = []
        if first_id is not None or second_id is not None:
            if first_id is None or second_id is None or first_id == second_id:
                return []
            owned = self._repository.owned_pair(user_id, {first_id, second_id})
            pairs = [tuple(owned)] if len(owned) == 2 else []
        else:
            pairs = list(combinations(self._repository.owned(user_id), 2))
        for first, second in pairs:
            first_notes = _weighted_keys(first, "note_links")
            second_notes = _weighted_keys(second, "note_links")
            shared_notes = sorted(set(first_notes) & set(second_notes))
            first_accords = _weighted_keys(first, "accord_links")
            second_accords = _weighted_keys(second, "accord_links")
            complementary = sorted(set(first_accords) ^ set(second_accords))
            seasons_a = {link.season: float(link.weight) for link in first.seasons}
            seasons_b = {link.season: float(link.weight) for link in second.seasons}
            season_overlap = max(
                (min(weight, seasons_b.get(season, 0.0)) for season, weight in seasons_a.items()),
                default=0.0,
            )
            shared_ratio = len(shared_notes) / max(len(set(first_notes) | set(second_notes)), 1)
            contrast_ratio = len(complementary) / max(
                len(set(first_accords) | set(second_accords)), 1
            )
            if mode == "safe":
                score = 0.5 * shared_ratio + 0.35 * season_overlap + 0.15 * (1 - contrast_ratio)
            elif mode == "contrast":
                score = 0.65 * contrast_ratio + 0.25 * season_overlap + 0.1 * shared_ratio
            else:
                score = 0.75 * contrast_ratio + 0.25 * (1 - shared_ratio)
            results.append(
                LayeringSuggestion(
                    first=to_fragrance_summary(first),
                    second=to_fragrance_summary(second),
                    mode=mode,
                    score=round(score, 4),
                    shared_notes=shared_notes,
                    complementary_accords=complementary,
                    season_overlap=round(season_overlap, 4),
                )
            )
        return sorted(
            results,
            key=lambda result: (-result.score, str(result.first.id), str(result.second.id)),
        )[: max(1, min(limit, 50))]
