import { Suspense } from "react";

import { ErrorState, LoadingState, UnavailableState } from "@/components/shared/states";
import { DashboardView } from "@/features/dashboard/dashboard-view";
import { ApiError } from "@/lib/server/api-client";
import { eventsOn, localDate, safeTimeZone, type CalendarResult } from "@/lib/calendar";
import {
  getCalendarAround,
  getInsights,
  getMe,
  getWearLogs,
  getWeather,
} from "@/lib/server/queries";
import type { WeatherResult } from "@/lib/weather";
import type { CollectionInsights, Me, WearLogEntry } from "@/types/api";

async function DashboardBoundary() {
  let me: Me;
  let insights: CollectionInsights;
  let recentWears: WearLogEntry[];
  let weather: WeatherResult;
  let calendar: CalendarResult;

  try {
    // Weather and calendar report provider trouble as a state rather than
    // throwing, so neither can fail the rest of the screen.
    [me, insights, recentWears, weather, calendar] = await Promise.all([
      getMe(),
      getInsights(),
      getWearLogs({ limit: 10 }),
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

  // The saved location's timezone decides what "today" means; UTC without one.
  const timeZone = safeTimeZone(me.preferences.timezone);
  const today = localDate(new Date(), timeZone);

  return (
    <DashboardView
      me={me}
      insights={insights}
      recentWears={recentWears}
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
