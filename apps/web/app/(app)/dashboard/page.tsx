import { Suspense } from "react";

import { ErrorState, LoadingState, UnavailableState } from "@/components/shared/states";
import { AtelierError, AtelierUnavailable } from "@/components/atelier/states";
import { DashboardView } from "@/features/dashboard/dashboard-view";
import { TodaySkeleton, TodayView } from "@/features/today/today-view";
import { WeekGlance, WeekGlanceSkeleton } from "@/features/today/week-glance";
import { ApiError } from "@/lib/server/api-client";
import { isAtelierEnabled } from "@/lib/atelier-flag";
import { eventsOn, localDate, safeTimeZone, type CalendarResult } from "@/lib/calendar";
import { getCalendarAround, getDashboardLite, getDashboardPage, getWeather } from "@/lib/server/queries";
import type { WeatherResult } from "@/lib/weather";
import { apiClient } from "@/lib/server/api-client";
import type { WearPlan } from "@/types/wear-intelligence";
import type { DashboardPageData, TemperatureUnit } from "@/types/api";

/** The week plan for Today's "This week" strip; any failure leaves just the link. */
async function TodayWeek({ today, unit }: { today: string; unit: TemperatureUnit | null }) {
  let plan: WearPlan | null = null;
  try {
    plan = await apiClient.get<WearPlan>("/api/v1/recommendations/week");
  } catch (error) {
    if (error instanceof ApiError && error.kind === "unauthorized") throw error;
    plan = null;
  }
  return <WeekGlance plan={plan} today={today} unit={unit} />;
}

async function DashboardBoundary({ atelier }: { atelier: boolean }) {
  let page: DashboardPageData;
  let weather: WeatherResult;
  let calendar: CalendarResult;
  // Started with the others so the pick never waits behind them. A failure here
  // degrades the pick, not the whole page.
  const planRequest = apiClient.get<WearPlan>("/api/v1/recommendations/today").then(
    (value): { plan?: WearPlan; failure?: unknown } => ({ plan: value }),
    (error: unknown): { plan?: WearPlan; failure?: unknown } => ({ failure: error }),
  );
  try {
    [page, weather, calendar] = await Promise.all([
      // Atelier's Today needs only the headline counts.
      atelier ? getDashboardLite() : getDashboardPage(),
      getWeather(),
      getCalendarAround(),
    ]);
  } catch (error) {
    if (error instanceof ApiError && error.kind === "unavailable") {
      return atelier ? <AtelierUnavailable /> : <UnavailableState />;
    }
    if (error instanceof ApiError) {
      return atelier ? <div className="at-page"><AtelierError message={error.message} /></div> : <ErrorState message={error.message} />;
    }
    throw error;
  }

  const { plan, failure } = await planRequest;
  if (failure !== undefined && !(failure instanceof ApiError)) throw failure;
  if (failure instanceof ApiError && failure.kind === "unauthorized") throw failure;
  const planFailed = failure !== undefined;
  const timeZone = safeTimeZone(page.me.preferences.timezone);
  const today = localDate(new Date(), timeZone);
  if (atelier) {
    const unit = weather.status === "ok" ? weather.forecast.temperature_unit : page.me.preferences.temperature_unit;
    return (
      <TodayView
        plan={plan}
        planFailed={planFailed}
        me={page.me}
        insights={page.insights}
        recentWears={page.recent_wears}
        weather={weather}
        calendar={eventsOn(calendar, today, timeZone)}
        timeZone={timeZone}
        week={page.insights.total_items > 0 ? (
          <Suspense fallback={<WeekGlanceSkeleton />}>
            <TodayWeek today={plan?.local_date ?? today} unit={unit} />
          </Suspense>
        ) : null}
      />
    );
  }
  return (
    <DashboardView
      plan={plan}
      me={page.me}
      insights={page.insights}
      recentWears={page.recent_wears}
      weather={weather}
      calendar={eventsOn(calendar, today, timeZone)}
      timeZone={timeZone}
    />
  );
}

export default function DashboardPage() {
  const atelier = isAtelierEnabled();
  return (
    <Suspense fallback={atelier ? <TodaySkeleton /> : <LoadingState rows={4} label="Loading your day" />}>
      <DashboardBoundary atelier={atelier} />
    </Suspense>
  );
}
