import { Suspense } from "react";

import { ErrorState, LoadingState, UnavailableState } from "@/components/shared/states";
import { DashboardView } from "@/features/dashboard/dashboard-view";
import { ApiError } from "@/lib/server/api-client";
import { getInsights, getMe, getWearLogs } from "@/lib/server/queries";
import type { CollectionInsights, Me, WearLogEntry } from "@/types/api";

async function DashboardBoundary() {
  let me: Me;
  let insights: CollectionInsights;
  let recentWears: WearLogEntry[];

  try {
    [me, insights, recentWears] = await Promise.all([
      getMe(),
      getInsights(),
      getWearLogs({ limit: 10 }),
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

  return <DashboardView me={me} insights={insights} recentWears={recentWears} />;
}

export default function DashboardPage() {
  return (
    <Suspense fallback={<LoadingState rows={4} label="Loading your day" />}>
      <DashboardBoundary />
    </Suspense>
  );
}
