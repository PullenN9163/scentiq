from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from itertools import combinations
from statistics import mean
from typing import Literal, cast
from uuid import UUID

from scentiq_api.errors import not_found, unprocessable
from scentiq_api.models import Fragrance, WearLog
from scentiq_api.models.layer_stacks import LayerStack, LayerStackItem, LayerStackWear
from scentiq_api.repositories import LayeringRepository
from scentiq_api.schemas import LayeringMode, LayeringSuggestion
from scentiq_api.schemas.layering import (
    LayeringGoal,
    LayeringIntelligencePage,
    LayeringStackSuggestion,
    LayeringStackWearResponse,
    SavedLayeringStack,
)
from scentiq_api.services.fragrances import to_fragrance_summary
from scentiq_api.services.layer_stack_scoring import (
    AUTO_COLLECTION_LIMIT,
    PAIR_BASE_LIMIT,
    THIRD_CANDIDATE_LIMIT,
    score_stack,
    supported_goals,
)


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

    def _inputs(
        self, user_id: UUID
    ) -> tuple[
        dict[UUID, float],
        int | None,
        dict[UUID, tuple[str | None, float | None]],
    ]:
        collection = self._repository.collection_items(user_id)
        counts = self._repository.wear_counts(user_id)
        preferences = self._repository.preferences(user_id)
        affinity = {
            item.fragrance_id: 0.5
            + ((item.user_rating or 3) - 3) * 0.1
            + min(counts.get(item.fragrance_id, 0), 10) * 0.01
            for item in collection
        }
        performance = {
            item.fragrance_id: (
                item.custom_projection,
                float(item.custom_longevity) if item.custom_longevity is not None else None,
            )
            for item in collection
        }
        return affinity, preferences.maximum_sprays if preferences else None, performance

    def _score(
        self,
        user_id: UUID,
        items: list[Fragrance],
        *,
        mode: LayeringMode,
        goal: LayeringGoal | None,
        history: list[LayerStack] | None = None,
        inputs: tuple[dict[UUID, float], int | None, dict[UUID, tuple[str | None, float | None]]]
        | None = None,
    ) -> LayeringStackSuggestion:
        affinity, maximum_sprays, performance = inputs or self._inputs(user_id)
        stack_ids = {item.id for item in items}
        ratings = [
            wear.rating
            for saved in (history if history is not None else self._repository.stacks(user_id))
            if {item.fragrance_id for item in saved.items} == stack_ids
            for wear in saved.wears
            if wear.rating is not None
        ]
        past = 0.5 + (mean(ratings) - 3) / 4 if ratings else 0.5
        return score_stack(
            items,
            mode=mode,
            goal=goal,
            affinity=affinity,
            history_affinity=past,
            maximum_sprays=maximum_sprays,
            performance=performance,
        )

    def evaluate_stack(
        self,
        user_id: UUID,
        fragrance_ids: list[UUID],
        *,
        mode: LayeringMode = "balanced",
        goal: LayeringGoal | None = None,
    ) -> LayeringStackSuggestion:
        if len(fragrance_ids) not in (2, 3) or len(set(fragrance_ids)) != len(fragrance_ids):
            raise unprocessable("invalid_stack", "Choose two or three distinct owned fragrances")
        owned = {item.id: item for item in self._repository.owned_pair(user_id, set(fragrance_ids))}
        if len(owned) != len(fragrance_ids):
            raise not_found("An owned fragrance was not found")
        inputs = self._inputs(user_id)
        if inputs[1] is not None and inputs[1] < len(fragrance_ids):
            raise unprocessable(
                "spray_budget_too_low",
                "Your spray ceiling must allow at least one spray for each fragrance in this stack",
            )
        return self._score(
            user_id,
            [owned[item_id] for item_id in fragrance_ids],
            mode=mode,
            goal=goal,
            inputs=inputs,
        )

    def stack_suggestions(
        self,
        user_id: UUID,
        *,
        anchor_id: UUID | None = None,
        mode: LayeringMode = "balanced",
        goal: LayeringGoal | None = None,
        limit: int = 12,
        include_triples: bool = True,
        stack_size: Literal[2, 3] | None = None,
    ) -> list[LayeringStackSuggestion]:
        owned = self._repository.owned(user_id)
        history = self._repository.stacks(user_id)
        inputs = self._inputs(user_id)
        if inputs[1] is not None and inputs[1] < 2:
            return []
        if inputs[1] is not None and inputs[1] < 3:
            include_triples = False
        if stack_size == 2:
            include_triples = False
        if anchor_id:
            anchors = [item for item in owned if item.id == anchor_id]
            if not anchors:
                raise not_found("Owned anchor fragrance not found")
        else:
            # Surprise mode remains bounded and deterministic, ordered by collection metadata.
            anchors = owned[:8]
        candidates = owned[:AUTO_COLLECTION_LIMIT]
        results: dict[tuple[UUID, ...], LayeringStackSuggestion] = {}
        for anchor in anchors:
            pairs = [
                self._score(
                    user_id, [anchor, item], mode=mode, goal=goal, history=history, inputs=inputs
                )
                for item in candidates
                if item.id != anchor.id
            ]
            pairs.sort(key=lambda value: (-value.score, str(value.items[1].fragrance.id)))
            for pair in pairs:
                key = tuple(sorted((item.fragrance.id for item in pair.items), key=str))
                results.setdefault(key, pair)
            if include_triples:
                by_id = {item.id: item for item in candidates}
                for pair in pairs[:PAIR_BASE_LIMIT]:
                    ids = [item.fragrance.id for item in pair.items]
                    supports = [item for item in candidates if item.id not in ids]
                    # Prioritize third candidates by their already-scored anchor pair.
                    rank = {item.items[1].fragrance.id: index for index, item in enumerate(pairs)}
                    supports.sort(key=lambda item: rank.get(item.id, AUTO_COLLECTION_LIMIT))
                    for third in supports[:THIRD_CANDIDATE_LIMIT]:
                        stack = self._score(
                            user_id,
                            [anchor, by_id[ids[1]], third],
                            mode=mode,
                            goal=goal,
                            history=history,
                            inputs=inputs,
                        )
                        if stack.score_components.overload_penalty >= 1:
                            continue
                        key = tuple(sorted([*ids, third.id], key=str))
                        results.setdefault(key, stack)
        ranked = sorted(
            (
                value
                for value in results.values()
                if stack_size is None or len(value.items) == stack_size
            ),
            key=lambda value: (
                -value.score,
                len(value.items),
                tuple(str(item.fragrance.id) for item in value.items),
            ),
        )
        return ranked[: max(1, min(limit, 50))]

    def intelligence_page(
        self,
        user_id: UUID,
        *,
        anchor_id: UUID | None = None,
        mode: LayeringMode = "balanced",
        goal: LayeringGoal | None = None,
    ) -> LayeringIntelligencePage:
        return LayeringIntelligencePage(
            supported_goals=supported_goals(self._repository.owned(user_id)),
            suggestions=self.stack_suggestions(user_id, anchor_id=anchor_id, mode=mode, goal=goal),
            saved=self.saved_stacks(user_id),
        )

    def _saved(
        self,
        user_id: UUID,
        stack: LayerStack,
        *,
        owned: dict[UUID, Fragrance] | None = None,
        inputs: tuple[dict[UUID, float], int | None, dict[UUID, tuple[str | None, float | None]]]
        | None = None,
        history: list[LayerStack] | None = None,
    ) -> SavedLayeringStack:
        ids = [item.fragrance_id for item in stack.items]
        owned = (
            owned
            if owned is not None
            else {item.id: item for item in self._repository.owned_pair(user_id, set(ids))}
        )
        if len(ids) not in (2, 3) or not all(item_id in owned for item_id in ids):
            raise not_found("A saved fragrance is no longer owned")
        inputs = inputs or self._inputs(user_id)
        below_ceiling = inputs[1] is not None and inputs[1] < len(ids)
        active_inputs = (inputs[0], None, inputs[2]) if below_ceiling else inputs
        suggestion = self._score(
            user_id,
            [owned[item_id] for item_id in ids],
            mode=cast(LayeringMode, stack.mode),
            goal=cast(LayeringGoal | None, stack.goal),
            inputs=active_inputs,
            history=history,
        )
        if below_ceiling:
            suggestion.warnings.append(
                "This saved plan exceeds your current spray ceiling; edit it before wearing."
            )
        ratings = [wear.rating for wear in stack.wears if wear.rating is not None]
        return SavedLayeringStack(
            id=stack.id,
            name=stack.name,
            notes=stack.notes,
            created_at=stack.created_at,
            last_worn_at=max((wear.worn_at for wear in stack.wears), default=None),
            average_rating=round(mean(ratings), 2) if ratings else None,
            wear_count=len(stack.wears),
            suggestion=suggestion,
        )

    def saved_stacks(self, user_id: UUID) -> list[SavedLayeringStack]:
        owned = {item.id: item for item in self._repository.owned(user_id)}
        inputs = self._inputs(user_id)
        history = self._repository.stacks(user_id)
        return [
            self._saved(user_id, stack, owned=owned, inputs=inputs, history=history)
            for stack in history
            if len(stack.items) >= 2 and all(item.fragrance_id in owned for item in stack.items)
        ]

    def save_stack(
        self,
        user_id: UUID,
        fragrance_ids: list[UUID],
        *,
        name: str,
        mode: LayeringMode = "balanced",
        goal: LayeringGoal | None = None,
        notes: str | None = None,
    ) -> SavedLayeringStack:
        if not name.strip() or len(name.strip()) > 120:
            raise unprocessable("invalid_name", "A combination name is required")
        suggestion = self.evaluate_stack(user_id, fragrance_ids, mode=mode, goal=goal)
        stack = LayerStack(
            user_id=user_id,
            name=name.strip(),
            mode=mode,
            goal=goal,
            notes=notes,
            score_snapshot=Decimal(str(suggestion.score)),
            evidence_coverage=Decimal(str(suggestion.evidence_coverage)),
            algorithm_version=suggestion.algorithm_version,
            score_components=suggestion.score_components.model_dump(),
        )
        stack.items = [
            LayerStackItem(
                fragrance_id=item.fragrance.id,
                position=index + 1,
                role=item.role,
                suggested_sprays=item.suggested_sprays,
            )
            for index, item in enumerate(suggestion.items)
        ]
        self._repository.add(stack)
        return self._saved(user_id, stack)

    def _owned_stack(self, user_id: UUID, stack_id: UUID) -> LayerStack:
        stack = self._repository.stack(user_id, stack_id)
        if stack is None:
            raise not_found("Saved combination not found")
        return stack

    def rename_stack(self, user_id: UUID, stack_id: UUID, name: str) -> SavedLayeringStack:
        if not name.strip() or len(name.strip()) > 120:
            raise unprocessable("invalid_name", "A combination name is required")
        stack = self._owned_stack(user_id, stack_id)
        stack.name = name.strip()
        self._repository.flush()
        return self._saved(user_id, stack)

    def delete_stack(self, user_id: UUID, stack_id: UUID) -> None:
        self._repository.delete(self._owned_stack(user_id, stack_id))

    @staticmethod
    def _wear_response(wear: LayerStackWear) -> LayeringStackWearResponse:
        return LayeringStackWearResponse(
            id=wear.id,
            stack_id=wear.stack_id,
            worn_at=wear.worn_at,
            rating=wear.rating,
            notes=wear.notes,
        )

    def history(self, user_id: UUID, stack_id: UUID) -> list[LayeringStackWearResponse]:
        stack = self._owned_stack(user_id, stack_id)
        return [
            self._wear_response(wear)
            for wear in sorted(stack.wears, key=lambda wear: wear.worn_at, reverse=True)
        ]

    def log_stack_wear(
        self,
        user_id: UUID,
        stack_id: UUID,
        *,
        worn_at: datetime | None = None,
        rating: int | None = None,
        notes: str | None = None,
    ) -> LayeringStackWearResponse:
        stack = self._owned_stack(user_id, stack_id)
        suggestion = self.evaluate_stack(
            user_id,
            [item.fragrance_id for item in stack.items],
            mode=cast(LayeringMode, stack.mode),
            goal=cast(LayeringGoal | None, stack.goal),
        )
        if rating is not None and rating not in range(1, 6):
            raise unprocessable("invalid_rating", "Rating must be between one and five")
        worn_at = worn_at or datetime.now(UTC)
        wear = LayerStackWear(
            user_id=user_id, stack_id=stack_id, worn_at=worn_at, rating=rating, notes=notes
        )
        stack.wears.append(wear)
        self._repository.flush()
        collection = {
            item.fragrance_id: item for item in self._repository.collection_items(user_id)
        }
        for item in suggestion.items:
            self._repository.add(
                WearLog(
                    user_id=user_id,
                    collection_item_id=collection[item.fragrance.id].id,
                    worn_at=worn_at,
                    sprays=item.suggested_sprays,
                    notes=notes,
                )
            )
        return self._wear_response(wear)

    def rate_stack_wear(
        self,
        user_id: UUID,
        stack_id: UUID,
        wear_id: UUID,
        *,
        rating: int,
    ) -> LayeringStackWearResponse:
        self._owned_stack(user_id, stack_id)
        wear = self._repository.stack_wear(user_id, stack_id, wear_id)
        if wear is None:
            raise not_found("Combination wear not found")
        if rating not in range(1, 6):
            raise unprocessable("invalid_rating", "Rating must be between one and five")
        wear.rating = rating
        self._repository.flush()
        return self._wear_response(wear)

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
