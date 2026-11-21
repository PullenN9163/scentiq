import { Suspense } from "react";

import { ErrorState, LoadingState, UnavailableState } from "@/components/shared/states";
import { InsightsView } from "@/features/insights/insights-view";
import { TasteBoundary } from "@/features/taste/taste-boundary";
import { TasteSkeleton } from "@/features/taste/taste-view";
import { isAtelierEnabled } from "@/lib/atelier-flag";
import { ApiError } from "@/lib/server/api-client";
import { getInsights } from "@/lib/server/queries";
import type { CollectionInsights } from "@/types/api";

async function InsightsBoundary() {
  let insights: CollectionInsights;

  try {
    insights = await getInsights();
  } catch (error) {
    if (error instanceof ApiError && error.kind === "unavailable") {
      return <UnavailableState />;
    }
    if (error instanceof ApiError) {
      return <ErrorState message={error.message} />;
    }
    throw error;
  }

  return <InsightsView insights={insights} />;
}

export default function InsightsPage() {
  if (isAtelierEnabled()) {
    return <Suspense fallback={<TasteSkeleton />}><TasteBoundary /></Suspense>;
  }
  return (
    <Suspense fallback={<LoadingState rows={5} label="Calculating your insights" />}>
      <InsightsBoundary />
    </Suspense>
  );
}
