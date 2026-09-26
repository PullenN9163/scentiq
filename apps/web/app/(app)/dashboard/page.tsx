import { Suspense } from "react";

import { ErrorState, LoadingState, UnavailableState } from "@/components/shared/states";
import { DashboardView } from "@/features/dashboard/dashboard-view";
import { ApiError } from "@/lib/server/api-client";
import { getInsights, getMe, getWearLogs, getWeather } from "@/lib/server/queries";
import type { WeatherResult } from "@/lib/weather";
import type { CollectionInsights, Me, WearLogEntry } from "@/types/api";

async function DashboardBoundary() {
  let me: Me;
  let insights: CollectionInsights;
  let recentWears: WearLogEntry[];
  let weather: WeatherResult;

  try {
    // `getWeather` reports provider trouble as a state rather than throwing,
    // so the forecast can never fail the rest of the screen.
    [me, insights, recentWears, weather] = await Promise.all([
      getMe(),
      getInsights(),
      getWearLogs({ limit: 10 }),
      getWeather(),
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

  return <DashboardView me={me} insights={insights} recentWears={recentWears} weather={weather} />;
}

export default function DashboardPage() {
  return (
    <Suspense fallback={<LoadingState rows={4} label="Loading your day" />}>
      <DashboardBoundary />
    </Suspense>
  );
}
