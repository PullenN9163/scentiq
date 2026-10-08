import { WeekPlanner } from "@/features/week/week-planner";
import { apiClient } from "@/lib/server/api-client";
import { getCalendarAround, getWeather } from "@/lib/server/queries";
import type { WearPlan } from "@/types/wear-intelligence";

export default async function WeekPage() {
  const [,calendar]=await Promise.all([getWeather(),getCalendarAround()]);
  const plan=await apiClient.get<WearPlan>("/api/v1/recommendations/week");
  return <WeekPlanner plan={plan} events={calendar.status === "ok" ? calendar.events : []}/>;
}
