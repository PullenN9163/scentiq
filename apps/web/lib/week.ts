import { dayBounds, localDate, occursOn, type CalendarResult } from "@/lib/calendar";
import { seasonForMonth, type RankingContext } from "@/lib/catalog-ranking";
import { isCool, type WeatherResult } from "@/lib/weather";
import type { CalendarEvent, ForecastDay, Occasion } from "@/types/api";

/** Turning forecasts and calendar events into per-day planning inputs. */

export interface PlanDay {
  /** Local calendar date, `YYYY-MM-DD`. */
  date: string;
  weather: ForecastDay | null;
  events: CalendarEvent[];
}

/** The member's next `count` local dates, starting today. */
export function nextDates(now: Date, timeZone: string, count = 7): string[] {
  const [year, month, day] = localDate(now, timeZone).split("-").map(Number);
  return Array.from({ length: count }, (_, offset) =>
    new Date(Date.UTC(year, month - 1, day + offset)).toISOString().slice(0, 10),
  );
}

/** The instants spanning a run of local dates, for fetching events. */
export function spanOf(dates: string[], timeZone: string): { start: Date; end: Date } {
  return {
    start: dayBounds(dates[0], timeZone).start,
    end: dayBounds(dates[dates.length - 1], timeZone).end,
  };
}

export function buildWeek(
  dates: string[],
  weather: WeatherResult,
  calendar: CalendarResult,
  timeZone: string,
): PlanDay[] {
  const forecasts = new Map(
    weather.status === "ok" ? weather.forecast.days.map((day) => [day.date, day]) : [],
  );
  const events = calendar.status === "ok" ? calendar.events : [];
  return dates.map((date) => ({
    date,
    weather: forecasts.get(date) ?? null,
    events: events.filter((event) => occursOn(event, date, timeZone)),
  }));
}

// When several events share a day, the one that most constrains a scent leads.
const OCCASION_PRIORITY: Occasion[] = [
  "formal",
  "date",
  "party",
  "dinner",
  "work",
  "travel",
  "gym",
  "casual",
];

export function leadOccasion(events: CalendarEvent[]): Occasion | null {
  for (const occasion of OCCASION_PRIORITY) {
    if (events.some((event) => event.occasion === occasion)) return occasion;
  }
  return null;
}

function localHour(instant: string, timeZone: string): number {
  return Number(
    new Intl.DateTimeFormat("en-US", { timeZone, hour: "2-digit", hourCycle: "h23" }).format(
      new Date(instant),
    ),
  );
}

/**
 * Ranking inputs for one day.
 *
 * Evening plans (a timed event from 17:00) favour night scents. Without a
 * forecast, autumn and winter count as cool.
 */
export function contextFor(day: PlanDay, timeZone: string): RankingContext {
  const season = seasonForMonth(Number(day.date.slice(5, 7)) - 1);
  const evening = day.events.some(
    (event) => !event.is_all_day && localHour(event.starts_at, timeZone) >= 17,
  );
  return {
    season,
    daypart: evening ? "night" : "day",
    coolWeather: day.weather ? isCool(day.weather) : season === "fall" || season === "winter",
    occasion: leadOccasion(day.events),
  };
}
