import { occasionLabel } from "@/lib/calendar";
import { conditionLabel, DEFAULT_TEMPERATURE_UNIT, toUnit } from "@/lib/weather";
import type { WeatherResult } from "@/lib/weather";
import type { CalendarEvent, TemperatureUnit, WeatherCondition, WearLogEntry } from "@/types/api";
import type { WearCandidate, WearPlan, WearRecommendation } from "@/types/wear-intelligence";

/** Reasons longer than this stay in the sentence rather than a chip. */
export const FACT_CHIP_MAX = 28;

/** "Saturday 14 November" for a `YYYY-MM-DD` local date. */
export function formatLongDate(localDate: string): string {
  return new Date(`${localDate}T12:00:00Z`).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" });
}

/** "Sun" for a `YYYY-MM-DD` local date. */
export function formatWeekday(localDate: string): string {
  return new Date(`${localDate}T12:00:00Z`).toLocaleDateString("en-GB", { weekday: "short", timeZone: "UTC" });
}

/** "22 Oct" in the member's time zone. */
export function formatShortDate(instant: string, timeZone: string): string {
  return new Date(instant).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone });
}

/** Today's weather as a short chip ("45°F cloudy"), or null when there is none. */
export function weatherChip(weather: WeatherResult, localDate: string): string | null {
  if (weather.status !== "ok") return null;
  const { forecast } = weather;
  const day = forecast.days.find((candidate) => candidate.date === localDate) ?? forecast.days[0];
  if (!day) return null;
  const unit = forecast.temperature_unit;
  const condition = day.condition === "unknown" ? "" : ` ${conditionLabel(day.condition).toLowerCase()}`;
  return `${toUnit(day.high_celsius, unit)}°${unit === "celsius" ? "C" : "F"}${condition}`;
}

/** A one-line forecast for a day cell or row ("41° rain"). */
export function shortForecast(highCelsius: number | null | undefined, condition: string | null | undefined, unit: TemperatureUnit | null | undefined): string | null {
  if (highCelsius === null || highCelsius === undefined) return null;
  const temperature = `${toUnit(highCelsius, unit ?? DEFAULT_TEMPERATURE_UNIT)}°`;
  const wet: Partial<Record<WeatherCondition, string>> = { rain: "rain", drizzle: "drizzle", snow: "snow", thunderstorm: "storms", fog: "fog" };
  const word = condition ? wet[condition as WeatherCondition] : undefined;
  return word ? `${temperature} ${word}` : temperature;
}

function asSentence(text: string): string {
  const trimmed = text.trim();
  if (!trimmed) return "";
  const capital = trimmed[0].toUpperCase() + trimmed.slice(1);
  return /[.!?]$/.test(capital) ? capital : `${capital}.`;
}

/**
 * Split the backend reasons into one short personal-fact chip and a one or
 * two sentence reason. Nothing is invented: both come from `reasons`.
 */
export function splitReasons(reasons: readonly string[]): { fact: string | null; sentence: string } {
  const clean = reasons.map((reason) => reason.trim()).filter(Boolean);
  const factIndex = clean.length > 1 ? clean.findIndex((reason) => reason.length <= FACT_CHIP_MAX) : -1;
  const fact = factIndex >= 0 ? clean[factIndex] : null;
  const rest = clean.filter((_, index) => index !== factIndex).slice(0, 2);
  return { fact, sentence: rest.map(asSentence).join(" ") };
}

/** The top accords line: the first one emphasised by the caller, the rest lower case. */
export function accordWords(accords: readonly string[]): string[] {
  return accords.slice(0, 3).map((accord, index) => (index === 0 ? accord[0]?.toUpperCase() + accord.slice(1) : accord.toLowerCase()));
}

/** "Tonight · Dinner at 19:30" style caption for a recommendation. */
export function recommendationCaption(recommendation: WearRecommendation, events: CalendarEvent[], timeZone: string): string {
  const { context } = recommendation;
  const parts = [context.daypart === "night" ? "Tonight" : "Today"];
  if (context.occasion) {
    const event = context.calendar_event_id ? events.find((candidate) => candidate.id === context.calendar_event_id) : undefined;
    const time = event && !event.is_all_day
      ? ` at ${new Date(event.starts_at).toLocaleTimeString("en-GB", { hour: "numeric", minute: "2-digit", timeZone })}`
      : "";
    parts.push(`${occasionLabel(context.occasion)}${time}`);
  }
  return parts.join(" · ");
}

/** "MYSLF Le Parfum, 22 Oct · The One, 21 Oct" from up to three recent wears. */
export function latelyLine(wears: readonly WearLogEntry[], timeZone: string): string | null {
  if (wears.length === 0) return null;
  return wears.slice(0, 3).map((wear) => `${wear.fragrance_name}, ${formatShortDate(wear.worn_at, timeZone)}`).join(" · ");
}

export type WeekGlanceEntry = {
  date: string;
  weekday: string;
  recommendation: WearRecommendation;
  caption: string;
  forecast: string | null;
};

/** The first pick for each day after `today`, in date order. */
export function weekGlance(plan: WearPlan | null, today: string, unit: TemperatureUnit | null | undefined): WeekGlanceEntry[] {
  if (!plan) return [];
  const byDate = new Map<string, WearRecommendation>();
  for (const recommendation of plan.recommendations as WearRecommendation[]) {
    const date = recommendation.context.local_date;
    if (date > today && !byDate.has(date)) byDate.set(date, recommendation);
  }
  return [...byDate.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, recommendation]) => ({
      date,
      weekday: formatWeekday(date),
      recommendation,
      caption: [formatWeekday(date), recommendation.context.occasion ? occasionLabel(recommendation.context.occasion).toLowerCase() : "open day"].join(" · "),
      forecast: shortForecast(recommendation.context.high_celsius, recommendation.context.condition, unit),
    }));
}

/** The candidate currently chosen for a recommendation (a saved replacement wins). */
export function selectedCandidate(recommendation: WearRecommendation): WearCandidate {
  return recommendation.alternatives.find((candidate) => candidate.fragrance.id === recommendation.decision?.selected_fragrance_id) ?? recommendation;
}

/** Sentence-case names for score components ("collection_fit" -> "Collection fit"). */
export function componentLabel(name: string): string {
  const words = name.replaceAll("_", " ").trim();
  return words ? words[0].toUpperCase() + words.slice(1) : name;
}
