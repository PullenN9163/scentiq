import { AtelierError, AtelierUnavailable } from "@/components/atelier/states";
import { RetryButton } from "@/features/fragrance/retry-button";
import { ApiError, apiClient } from "@/lib/server/api-client";
import { safeTimeZone } from "@/lib/calendar";
import { getCalendarRange, getInsightsSummary, getMe, getWeather } from "@/lib/server/queries";
import { spanOf } from "@/lib/week";
import type { CalendarResult } from "@/lib/calendar";
import type { WeatherResult } from "@/lib/weather";
import type { CollectionInsights, Me } from "@/types/api";
import type { WearPlan } from "@/types/wear-intelligence";

import { addDays } from "./week-copy";
import { WeekView } from "./week-view";

/** Loads the week plan, forecast and events for the Atelier Week. */
export async function WeekBoundary() {
  let plan: WearPlan;
  let me: Me;
  let weather: WeatherResult;
  let insights: CollectionInsights | null = null;
  try {
    [plan, me, weather, insights] = await Promise.all([
      apiClient.get<WearPlan>("/api/v1/recommendations/week"),
      getMe(),
      getWeather(),
      getInsightsSummary().catch((error: unknown) => { if (error instanceof ApiError && error.kind === "unauthorized") throw error; return null; }),
    ]);
  } catch (error) {
    if (error instanceof ApiError && error.kind === "unavailable") return <AtelierUnavailable retry={<RetryButton />} />;
    if (error instanceof ApiError) return <div className="at-page"><AtelierError title="Your week did not load" message={error.message} retry={<RetryButton />} /></div>;
    throw error;
  }
  const timeZone = safeTimeZone(plan.timezone || me.preferences.timezone);
  const dates = Array.from({ length: 7 }, (_, index) => addDays(plan.local_date, index));
  const span = spanOf(dates, timeZone);
  const calendar: CalendarResult = await getCalendarRange(span.start, span.end);
  const forecast = weather.status === "ok" ? weather.forecast.days : [];
  const unit = weather.status === "ok" ? weather.forecast.temperature_unit : me.preferences.temperature_unit;
  return (
    <WeekView
      plan={plan}
      calendar={calendar}
      forecast={forecast}
      location={me.preferences.location_label ?? me.preferences.location}
      timeZone={timeZone}
      unit={unit}
      emptyCollection={insights?.total_items === 0}
    />
  );
}
