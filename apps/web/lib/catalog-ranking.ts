import type { Occasion, Projection, Season, WeekFragrance } from "@/types/api";

const projectionScores: Record<Projection, number> = {
  intimate: 0.35,
  moderate: 0.7,
  strong: 1,
};

export interface RankingContext {
  season: Season;
  daypart: "day" | "night";
  coolWeather: boolean;
  /** The day's main calendar occasion, when a connected calendar supplies one. */
  occasion?: Occasion | null;
}

export function seasonForMonth(month: number): Season {
  if (month >= 2 && month <= 4) return "spring";
  if (month >= 5 && month <= 7) return "summer";
  if (month >= 8 && month <= 10) return "fall";
  return "winter";
}

/** Rank catalog-backed collection details with only recorded recommendation signals. */
export function rankFragrances(
  fragrances: WeekFragrance[],
  context: RankingContext,
): WeekFragrance[] {
  const score = (fragrance: WeekFragrance) => {
    const season = fragrance.seasons.find((entry) => entry.season === context.season)?.weight ?? 0;
    const dayVotes = fragrance.community?.day_votes ?? 0;
    const nightVotes = fragrance.community?.night_votes ?? 0;
    const daypartVotes = context.daypart === "day" ? dayVotes : nightVotes;
    const daypart = dayVotes + nightVotes > 0 ? daypartVotes / (dayVotes + nightVotes) : 0;
    const longevity = fragrance.longevity_score === null ? 0 : fragrance.longevity_score / 10;
    const weatherLongevity = context.coolWeather ? longevity : 1 - longevity;
    const projection = fragrance.projection_level
      ? projectionScores[fragrance.projection_level]
      : 0;
    const occasion = context.occasion
      ? (fragrance.occasions.find((entry) => entry.occasion === context.occasion)?.weight ?? 0)
      : 0;
    return (
      season * 0.4 + daypart * 0.25 + weatherLongevity * 0.2 + projection * 0.15 + occasion * 0.3
    );
  };

  return [...fragrances].sort(
    (first, second) => score(second) - score(first) || first.id.localeCompare(second.id),
  );
}
