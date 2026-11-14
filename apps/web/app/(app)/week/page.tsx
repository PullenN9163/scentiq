import { Suspense } from "react";

import { WeekPlanner } from "@/features/week/week-planner";
import { WeekBoundary } from "@/features/week-atelier/week-boundary";
import { WeekSkeleton } from "@/features/week-atelier/week-view";
import { isAtelierEnabled } from "@/lib/atelier-flag";
import { apiClient } from "@/lib/server/api-client";
import { getCalendarAround, getWeather } from "@/lib/server/queries";
import type { WearPlan } from "@/types/wear-intelligence";

export default async function WeekPage() {
  if (isAtelierEnabled()) {
    return <Suspense fallback={<WeekSkeleton />}><WeekBoundary /></Suspense>;
  }
  const [,calendar]=await Promise.all([getWeather(),getCalendarAround()]);
  const plan=await apiClient.get<WearPlan>("/api/v1/recommendations/week");
  return <WeekPlanner plan={plan} events={calendar.status === "ok" ? calendar.events : []}/>;
}
