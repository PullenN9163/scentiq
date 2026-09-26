import { AgentExperience } from "@/features/agent/agent-experience";
import {
  getCollection,
  getFragrance,
  getInsights,
  getLayeringSuggestions,
} from "@/lib/server/queries";

export default async function AgentPage() {
  const [collection, insights, layering] = await Promise.all([getCollection(), getInsights(), getLayeringSuggestions("safe")]);
  const owned = collection.filter((item) => item.status === "owned");
  const details = await Promise.all(owned.map((item) => getFragrance(item.fragrance.id)));
  return <AgentExperience owned={details} insights={insights} layering={layering} />;
}
