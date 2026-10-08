"""Pure deterministic wear scoring. Missing metadata receives neutral points."""

from uuid import UUID

from pydantic import BaseModel, Field

from scentiq_api.schemas.wear_recommendations import RecommendationContext

WEAR_ALGORITHM_VERSION = "wear-v1"


class CandidateInput(BaseModel):
    fragrance_id: UUID
    projection: str | None = None
    longevity: float | None = None
    season_weights: dict[str, float] = Field(default_factory=dict)
    occasion_weights: dict[str, float] = Field(default_factory=dict)
    day_votes: int | None = None
    night_votes: int | None = None
    rating: int | None = None
    feedback_rating: float | None = None
    occasion_history_rating: float | None = None
    days_since_wear: float | None = None
    wears_last_30_days: int = 0
    rejections: int = 0


class ScoredCandidate(BaseModel):
    score: float
    components: dict[str, float]
    evidence_coverage: float
    sprays: int
    reasons: list[str]
    warnings: list[str]


def score_candidate(
    item: CandidateInput,
    context: RecommendationContext,
    *,
    maximum_sprays: int | None = None,
    preferred_projection: str | None = None,
    preferred_longevity: float | None = None,
) -> ScoredCandidate:
    occasion = 12.5
    occasion_evidence = False
    if context.occasion is not None and item.occasion_weights:
        occasion = 25 * item.occasion_weights.get(context.occasion, 0)
        occasion_evidence = True
    elif context.occasion is not None and item.occasion_history_rating is not None:
        occasion = 12.5 + 2.5 * (item.occasion_history_rating - 3)
        occasion_evidence = True
    temperature = context.high_celsius
    weather = 10.0
    weather_evidence = temperature is not None and item.projection is not None
    warnings: list[str] = []
    hot = temperature is not None and temperature >= 28
    cold = temperature is not None and temperature <= 5
    if weather_evidence:
        weather = 15
        if hot and (item.projection == "strong" or (item.longevity or 0) >= 8):
            weather = 6
            warnings.append("Heat and strong performance: start with fewer sprays.")
        elif cold and context.setting == "outdoor" and item.projection == "intimate":
            weather = 7
            warnings.append("Intimate projection may be less noticeable outdoors in the cold.")
    season = 15 * item.season_weights.get(context.season, 0) if item.season_weights else 7.5
    conservative = (
        context.setting == "indoor"
        or context.occasion in ("work", "formal")
        or context.formality == "formal"
    )
    setting_evidence = item.projection is not None and (
        context.setting is not None or context.occasion in ("work", "formal")
    )
    setting = 5.0
    if setting_evidence:
        setting = 9 if item.projection != "strong" or not conservative else 3
    if conservative and item.projection == "strong":
        warnings.append("Strong projection — start lighter indoors.")
    day_votes, night_votes = item.day_votes or 0, item.night_votes or 0
    time_evidence = day_votes + night_votes > 0
    time_score = (
        (
            10
            * ((day_votes if context.daypart == "day" else night_votes) / (day_votes + night_votes))
        )
        if time_evidence
        else 5.0
    )
    preference = 5.0
    if item.rating is not None:
        preference += item.rating - 3
    if item.feedback_rating is not None:
        preference += max(-2, min(2, item.feedback_rating - 3))
    if preferred_projection is not None and item.projection is not None:
        preference += 1 if preferred_projection == item.projection else -1
    if preferred_longevity is not None and item.longevity is not None:
        preference += max(-1, 1 - abs(item.longevity - preferred_longevity) / 3)
    preference = max(0, min(10, preference))
    days = item.days_since_wear
    rotation = 10 if days is None or days >= 7 else (8 if days >= 3 else (5 if days >= 1 else 2))
    penalties = 0.0
    if days is not None:
        penalties -= 8 if days < 1 else (4 if days < 3 else 0)
    penalties -= min(6, item.wears_last_30_days)
    penalties -= min(8, item.rejections * 2)
    if conservative and item.projection == "strong":
        penalties -= 4
    if hot and weather == 6:
        penalties -= 4
    penalties = max(-30, penalties)
    components = {
        "occasion": occasion,
        "weather": weather,
        "season": season,
        "setting_projection": setting,
        "time_of_day": time_score,
        "user_preference": preference,
        "rotation": float(rotation),
        "penalties": penalties,
    }
    evidence = [
        occasion_evidence,
        weather_evidence,
        bool(item.season_weights),
        setting_evidence,
        time_evidence,
        item.rating is not None
        or item.feedback_rating is not None
        or (preferred_projection is not None and item.projection is not None)
        or (preferred_longevity is not None and item.longevity is not None),
        True,
    ]
    sprays = {"intimate": 5, "moderate": 4, "strong": 3}.get(item.projection or "", 4)
    sprays -= int(hot) + int(conservative)
    sprays += int(cold and context.setting == "outdoor" and item.projection == "intimate")
    sprays = max(1, min(8, sprays, maximum_sprays if maximum_sprays is not None else 8))
    positives = [
        (season / 15, "Source-backed seasonal match", bool(item.season_weights)),
        (occasion / 25, "Fits recorded occasion evidence", occasion_evidence),
        (setting / 10, "Projection suits this setting", setting_evidence),
        (time_score / 10, "Community day/night votes fit this time", time_evidence),
        (preference / 10, "Matches your ratings and preferences", evidence[5]),
        (rotation / 10, "You have not worn it recently", rotation >= 8),
        (weather / 20, "Performance fits the weather guidance", weather_evidence),
    ]
    reasons = [
        label
        for fit, label, supported in sorted(positives, key=lambda p: (-p[0], p[1]))
        if supported and fit > 0.5
    ][:3]
    if sum(evidence) < 3:
        warnings.append("Limited catalog evidence; missing signals receive neutral scores.")
    return ScoredCandidate(
        score=round(max(0, min(100, sum(components.values()))), 2),
        components=components,
        evidence_coverage=sum(evidence) / 7,
        sprays=sprays,
        reasons=reasons,
        warnings=warnings,
    )
