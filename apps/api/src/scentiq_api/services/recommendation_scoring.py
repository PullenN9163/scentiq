"""Portable formulas shared by interactive and background recommendation paths."""


def discovery_score(
    taste: float,
    expansion: float,
    risk: float,
    *,
    mode: str = "balance",
    season_fit: float | None = None,
    affinity: float = 0,
) -> float:
    if mode == "taste":
        score = 0.80 * taste + 0.15 * expansion - 0.10 * risk
    elif mode == "explore":
        score = 0.15 * taste + 0.70 * expansion - 0.35 * risk
    elif mode == "seasonal":
        score = 0.35 * taste + 0.25 * expansion + 0.40 * (season_fit or 0) - 0.20 * risk
    else:
        score = 0.55 * taste + 0.35 * expansion - 0.25 * risk
    return score + 0.3 * affinity


def pair_score(
    shared: float, contrast: float, season: float, mode: str, affinity: float = 0
) -> float:
    if mode == "safe":
        score = 0.5 * shared + 0.35 * season + 0.15 * (1 - contrast)
    elif mode == "contrast":
        score = 0.65 * contrast + 0.25 * season + 0.1 * shared
    else:
        score = 0.75 * contrast + 0.25 * (1 - shared)
    return max(0, min(1, score + 0.15 * affinity))


def feature_affinity(
    features: dict[str, float], *, accords: set[str], notes: set[str], family: str | None
) -> float:
    keys = {f"accord:{key}" for key in accords} | {f"note:{key}" for key in notes}
    if family:
        keys.add("family:" + family.casefold().replace(" ", "-"))
    values = [features[key] for key in keys if key in features]
    return sum(values) / len(values) if values else 0


def positive_taste_overlap(
    accords: dict[str, float],
    notes: set[str],
    owned_accords: set[str],
    owned_notes: set[str],
    features: dict[str, float],
) -> float:
    """Dislikes never become positive matches; unrated ownership is weak evidence."""
    accord_overlap = sum(
        weight * max(0, features.get(f"accord:{key}", 0.5 if key in owned_accords else 0))
        for key, weight in accords.items()
    ) / (sum(accords.values()) or 1)
    note_overlap = sum(
        max(0, features.get(f"note:{key}", 0.5 if key in owned_notes else 0)) for key in notes
    ) / (len(notes) or 1)
    observed_channels = int(bool(accords)) + int(bool(notes))
    return (accord_overlap + note_overlap) / observed_channels if observed_channels else 0
