import { Suspense } from "react";

import { ErrorState, LoadingState, UnavailableState } from "@/components/shared/states";
import { DashboardView } from "@/features/dashboard/dashboard-view";
import { ApiError } from "@/lib/server/api-client";
import { eventsOn, localDate, safeTimeZone, type CalendarResult } from "@/lib/calendar";
import { getCalendarAround, getDashboardPage, getWeather } from "@/lib/server/queries";
import type { WeatherResult } from "@/lib/weather";
import type { DashboardPageData } from "@/types/api";

async function DashboardBoundary() {
  let page: DashboardPageData;
  let weather: WeatherResult;
  let calendar: CalendarResult;
  try {
    [page, weather, calendar] = await Promise.all([
      getDashboardPage(),
      getWeather(),
      getCalendarAround(),
    ]);
  } catch (error) {
    if (error instanceof ApiError && error.kind === "unavailable") {
      return <UnavailableState />;
    }
    if (error instanceof ApiError) {
      return <ErrorState message={error.message} />;
    }
    throw error;
  }

  const timeZone = safeTimeZone(page.me.preferences.timezone);
  const today = localDate(new Date(), timeZone);
  return (
    <DashboardView
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
  return (
    <Suspense fallback={<LoadingState rows={4} label="Loading your day" />}>
      <DashboardBoundary />
    </Suspense>
  );
}
