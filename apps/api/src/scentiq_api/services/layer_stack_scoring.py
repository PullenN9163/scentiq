"""Pure olfactory stack scoring. All performance/application advice is a starting point."""

from __future__ import annotations

from itertools import combinations
from statistics import mean
from uuid import UUID

from scentiq_api.models.catalog import Fragrance
from scentiq_api.schemas.layering import (
    LayeringGoal,
    LayeringMode,
    LayeringRole,
    LayeringScoreComponents,
    LayeringStackItem,
    LayeringStackSuggestion,
)
from scentiq_api.services.fragrances import to_fragrance_summary

LAYERING_ALGORITHM_VERSION = "layering-v2"
PAIR_BASE_LIMIT = 8
THIRD_CANDIDATE_LIMIT = 16
AUTO_COLLECTION_LIMIT = 200
GOAL_SIGNALS: dict[str, set[str]] = {
    "fresher": {"citrus", "fresh", "green", "aromatic", "aquatic", "fresh-spicy"},
    "warmer": {"amber", "vanilla", "spicy", "warm-spicy", "woody", "resin", "tobacco", "gourmand"},
    "sweeter": {"sweet", "vanilla", "gourmand", "fruity", "honey", "caramel"},
    "darker": {"oud", "leather", "smoky", "tobacco", "incense", "patchouli", "woody"},
    "cleaner": {"fresh", "musky", "soapy", "citrus", "aldehydic", "aquatic"},
    "daytime": {"citrus", "fresh", "green", "aquatic", "aromatic"},
    "evening": {"amber", "woody", "vanilla", "leather", "tobacco", "warm-spicy"},
}
MODE_WEIGHTS = {
    "balanced": (0.22, 0.20, 0.13, 0.12, 0.08, 0.10, 0.15),
    "safe": (0.32, 0.10, 0.17, 0.16, 0.08, 0.02, 0.15),
    "contrast": (0.18, 0.27, 0.10, 0.12, 0.08, 0.15, 0.10),
    "experimental": (0.17, 0.25, 0.08, 0.12, 0.08, 0.20, 0.10),
}
PROJECTION = {"intimate": 0.25, "moderate": 0.55, "strong": 0.9}


def signals(item: Fragrance) -> dict[str, float]:
    output = {link.accord.slug: float(link.weight) for link in item.accord_links}
    for link in item.note_links:
        output[link.note.slug] = max(output.get(link.note.slug, 0), float(link.weight or 0.5))
    if item.olfactory_family:
        output.setdefault(item.olfactory_family.lower().replace(" ", "-"), 0.5)
    return output


def overlap(first: dict[str, float], second: dict[str, float]) -> float:
    union = set(first) | set(second)
    total = sum(max(first.get(key, 0), second.get(key, 0)) for key in union)
    return sum(min(first.get(key, 0), second.get(key, 0)) for key in union) / total if total else 0


def projection(item: Fragrance) -> float | None:
    if item.projection_level:
        return PROJECTION.get(item.projection_level)
    if item.community and item.community.sillage_average is not None:
        return min(1, float(item.community.sillage_average) / 4)
    return None


def supported_goals(items: list[Fragrance]) -> list[LayeringGoal]:
    all_signals = set().union(*(signals(item) for item in items)) if items else set()
    goals: list[LayeringGoal] = []
    for goal in ("fresher", "warmer", "sweeter", "darker", "cleaner", "daytime", "evening"):
        if all_signals & GOAL_SIGNALS[goal]:
            goals.append(goal)
    if any(projection(item) is not None for item in items):
        goals.extend(["softer", "more_projection", "more_intimate"])
    seasons = {link.season for item in items for link in item.seasons}
    goals.extend(season for season in ("spring", "summer", "fall", "winter") if season in seasons)
    return goals


def score_stack(
    items: list[Fragrance],
    *,
    mode: LayeringMode = "balanced",
    goal: LayeringGoal | None = None,
    affinity: dict[UUID, float] | None = None,
    history_affinity: float = 0.5,
    maximum_sprays: int | None = None,
    performance: dict[UUID, tuple[str | None, float | None]] | None = None,
) -> LayeringStackSuggestion:
    if len(items) not in (2, 3) or len({item.id for item in items}) != len(items):
        raise ValueError("A stack needs two or three distinct fragrances")
    if maximum_sprays is not None and maximum_sprays < len(items):
        raise ValueError("Spray ceiling cannot support this many fragrances")
    profiles = [signals(item) for item in items]
    edges = {
        (i, j): overlap(profiles[i], profiles[j]) for i, j in combinations(range(len(items)), 2)
    }
    bridge_index = 1
    if len(items) == 3:
        # The bridge must connect the anchor to the accent, not merely duplicate one scent.
        bridge_index = max(
            (1, 2),
            key=lambda i: min(edges[0, i], edges[1, 2]),
        )
        bridge = min(
            edges[0, bridge_index],
            edges[1, 2],
        )
    else:
        bridge = edges[0, 1]
    redundancy = max(edges.values())
    contribution = mean(
        sum(weight for key, weight in profile.items() if key not in profiles[0])
        / (sum(profile.values()) or 1)
        for profile in profiles[1:]
    )
    complement = contribution * min(1, bridge * 2 + 0.25)
    season_maps = [{link.season: float(link.weight) for link in item.seasons} for item in items]
    common_seasons = set.intersection(*(set(mapping) for mapping in season_maps))
    season_fit = max(
        (min(mapping[season] for mapping in season_maps) for season in common_seasons), default=0.5
    )
    projections = [
        PROJECTION.get((performance or {}).get(item.id, (None, None))[0] or "")
        if (performance or {}).get(item.id, (None, None))[0]
        else projection(item)
        for item in items
    ]
    longevity_values = [
        (performance or {}).get(item.id, (None, None))[1]
        if (performance or {}).get(item.id, (None, None))[1] is not None
        else float(item.longevity_score)
        if item.longevity_score is not None
        else None
        for item in items
    ]
    known_projection = [value for value in projections if value is not None]
    target = (
        0.75 if goal == "more_projection" else 0.3 if goal in ("softer", "more_intimate") else 0.5
    )
    projection_balance = (
        max(0, 1 - abs(mean(known_projection) - target)) if known_projection else 0.5
    )
    strong_count = sum(value is not None and value >= 0.8 for value in projections)
    overload = min(1, max(0, strong_count - 1) * 0.5)
    if goal in ("softer", "more_intimate"):
        overload = max(overload, strong_count / len(items))
    longevity = [value / 10 for value in longevity_values if value is not None]
    longevity_balance = 1 - (max(longevity) - min(longevity)) if len(longevity) >= 2 else 0.5
    user_affinity = mean((affinity or {}).get(item.id, 0.5) for item in items)
    user_affinity = max(0, min(1, user_affinity + (history_affinity - 0.5) * 0.5))
    components = LayeringScoreComponents(
        bridge=round(bridge, 4),
        complement=round(complement, 4),
        season_context=round(season_fit, 4),
        projection_balance=round(projection_balance, 4),
        longevity_balance=round(longevity_balance, 4),
        novelty=round(contribution, 4),
        user_affinity=round(user_affinity, 4),
        redundancy_penalty=round(redundancy, 4),
        overload_penalty=round(overload, 4),
    )
    base = sum(
        weight * value
        for weight, value in zip(
            MODE_WEIGHTS[mode],
            (
                bridge,
                complement,
                season_fit,
                projection_balance,
                longevity_balance,
                contribution,
                user_affinity,
            ),
            strict=True,
        )
    )
    goal_fit: float | None = None
    if goal in GOAL_SIGNALS:
        goal_fit = mean(
            sum(value for key, value in profile.items() if key in GOAL_SIGNALS[goal])
            / (sum(profile.values()) or 1)
            for profile in profiles[1:]
        )
        if goal in ("daytime", "evening"):
            votes: list[float] = []
            for item in items[1:]:
                community = item.community
                if community and (community.day_votes or community.night_votes):
                    total = (community.day_votes or 0) + (community.night_votes or 0)
                    votes.append(
                        ((community.day_votes if goal == "daytime" else community.night_votes) or 0)
                        / total
                    )
            if votes:
                goal_fit = (goal_fit + mean(votes)) / 2
    elif goal in ("spring", "summer", "fall", "winter"):
        goal_fit = mean(mapping.get(goal, 0) for mapping in season_maps)
    elif goal in ("softer", "more_intimate", "more_projection"):
        goal_fit = projection_balance
    if goal_fit is not None:
        base = 0.70 * base + 0.30 * goal_fit
    score = max(0, min(1, base - 0.18 * redundancy - 0.22 * overload))
    coverage = mean(
        mean(
            (
                bool(item.note_links),
                bool(item.accord_links),
                bool(item.seasons),
                projections[index] is not None,
                longevity_values[index] is not None,
            )
        )
        for index, item in enumerate(items)
    )
    warnings = []
    if coverage < 0.65:
        warnings.append("Limited evidence: some notes, seasons or performance signals are missing.")
    if redundancy > 0.7:
        warnings.append(
            "High overlap may repeat the same profile instead of adding a distinct role."
        )
    if overload > 0:
        warnings.append("Several projecting scents may dominate together; start with fewer sprays.")
    if bridge < 0.15:
        warnings.append("Few recorded bridging signals; this contrast is less predictable.")
    total = (
        3 if goal in ("softer", "more_intimate") or strong_count >= 2 else 4 if strong_count else 6
    )
    if coverage < 0.65:
        total = min(total, 4)
    total = max(len(items), min(total, maximum_sprays or 6))
    # One spray per supporting role; allocate extra to anchor first, then bridge.
    sprays = [1] * len(items)
    for index in range(total - len(items)):
        sprays[0 if index % 2 == 0 else bridge_index] += 1
    order = sorted(
        range(len(items)),
        key=lambda index: (
            -(projections[index] or 0.5),
            -(longevity_values[index] or 5),
            index,
        ),
    )
    shared_notes = sorted(
        set.intersection(*({link.note.slug for link in item.note_links} for item in items))
    )
    shared_accords = sorted(
        set.intersection(*({link.accord.slug for link in item.accord_links} for item in items))
    )
    bridge_signals = sorted(set(profiles[0]) & set(profiles[bridge_index]))
    if len(items) == 3:
        bridge_signals = sorted(
            set(bridge_signals) | (set(profiles[bridge_index]) & set(profiles[3 - bridge_index]))
        )
    complementary = sorted(
        set.union(*(set(profile) for profile in profiles[1:])) - set(profiles[0])
    )
    roles: list[LayeringRole] = ["anchor"]
    for _ in items[1:]:
        roles.append("accent")
    if len(items) == 3:
        roles[bridge_index] = "bridge"
    reasons = [
        "Recorded shared notes/accords: " + (", ".join(bridge_signals[:6]) or "none available"),
        "Supporting scents add recorded signals: "
        + (", ".join(complementary[:6]) or "a closely related profile"),
        "Rule-based starting guidance: apply the stronger/longer-lasting scent first, "
        "then lighter accents.",
    ]
    if goal:
        reasons.append(
            f"Goal {goal.replace('_', ' ')} uses supported profile and performance signals."
        )
    return LayeringStackSuggestion(
        items=[
            LayeringStackItem(
                fragrance=to_fragrance_summary(item),
                role=roles[index],
                application_order=order.index(index) + 1,
                suggested_sprays=sprays[index],
            )
            for index, item in enumerate(items)
        ],
        mode=mode,
        goal=goal,
        score=round(score, 4),
        score_components=components,
        shared_notes=shared_notes,
        shared_accords=shared_accords,
        bridge_signals=bridge_signals,
        complementary_signals=complementary,
        best_contexts=sorted(common_seasons) + ([goal] if goal in ("daytime", "evening") else []),
        reasons=reasons,
        warnings=warnings,
        total_sprays=total,
        evidence_coverage=round(coverage, 4),
        evidence_label="strong"
        if coverage >= 0.85
        else "partial"
        if coverage >= 0.65
        else "limited",
    )
