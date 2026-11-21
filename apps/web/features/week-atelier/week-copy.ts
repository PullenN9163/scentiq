import { dayBounds, occursOn } from "@/lib/calendar";
import { shortForecast } from "@/features/today/today-copy";
import type { CalendarEvent, ForecastDay, TemperatureUnit } from "@/types/api";
import type { WearPlan, WearRecommendation } from "@/types/wear-intelligence";

export type WeekDay = {
  date: string;
  /** "Sat 14" */
  label: string;
  isToday: boolean;
  recommendations: WearRecommendation[];
  events: CalendarEvent[];
  forecast: ForecastDay | null;
  /** "41° rain" */
  forecastLabel: string | null;
};

export function addDays(date: string, days: number): string {
  const value = new Date(`${date}T12:00:00Z`);
  value.setUTCDate(value.getUTCDate() + days);
  return value.toISOString().slice(0, 10);
}

export function dayLabel(date: string): string {
  return new Date(`${date}T12:00:00Z`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", timeZone: "UTC" });
}

/** "14 to 20 November" (or "28 November to 4 December"). */
export function rangeLabel(first: string, last: string): string {
  const format = (date: string, month: boolean) => new Date(`${date}T12:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", ...(month ? { month: "long" } : {}), timeZone: "UTC" });
  const sameMonth = first.slice(0, 7) === last.slice(0, 7);
  return `${format(first, !sameMonth)} to ${format(last, true)}`;
}

/** Seven days from the plan's local date, with picks, events and forecast. */
export function buildWeek(plan: WearPlan, events: readonly CalendarEvent[], forecast: readonly ForecastDay[], timeZone: string, unit: TemperatureUnit | null | undefined): WeekDay[] {
  const recommendations = plan.recommendations as WearRecommendation[];
  return Array.from({ length: 7 }, (_, index) => {
    const date = addDays(plan.local_date, index);
    const dayRecommendations = recommendations.filter((recommendation) => recommendation.context.local_date === date);
    const dayForecast = forecast.find((day) => day.date === date) ?? null;
    const fromContext = dayRecommendations.find((recommendation) => recommendation.context.high_celsius != null)?.context;
    const forecastLabel = dayForecast
      ? shortForecast(dayForecast.high_celsius, dayForecast.condition, unit)
      : fromContext ? shortForecast(fromContext.high_celsius, fromContext.condition, unit) : null;
    return {
      date,
      label: dayLabel(date),
      isToday: index === 0,
      recommendations: dayRecommendations,
      events: events.filter((event) => occursOn(event, date, timeZone)).sort((a, b) => a.starts_at.localeCompare(b.starts_at)),
      forecast: dayForecast,
      forecastLabel,
    };
  });
}

/** An instant inside the selected local day (noon), for logging a wear on that day. */
export function noonOf(date: string, timeZone: string): string {
  const { start } = dayBounds(date, timeZone);
  return new Date(start.getTime() + 12 * 60 * 60 * 1000).toISOString();
}

/** "Office +2" for a day cell. */
export function eventSummary(events: readonly CalendarEvent[]): string | null {
  if (events.length === 0) return null;
  return events.length > 1 ? `${events[0].title} +${events.length - 1}` : events[0].title;
}
