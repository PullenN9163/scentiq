import { WeekPlanner } from "@/features/week/week-planner";
import { getCollection, getFragrance } from "@/lib/server/queries";

export default async function WeekPage() {
  const collection = await getCollection();
  const owned = collection.filter((item) => item.status === "owned");
  const details = await Promise.all(owned.map((item) => getFragrance(item.fragrance.id)));
  return <WeekPlanner owned={details} />;
}
