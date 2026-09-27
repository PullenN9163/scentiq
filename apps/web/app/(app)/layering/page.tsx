import { LayeringLab } from "@/features/layering/layering-lab";
import { getCollection, getLayeringSuggestions } from "@/lib/server/queries";

export default async function LayeringPage({ searchParams }: { searchParams: Promise<{ a?: string }> }) {
  const { a } = await searchParams;
  const [collection, safe, contrast, experimental] = await Promise.all([
    getCollection(),
    getLayeringSuggestions("safe"),
    getLayeringSuggestions("contrast"),
    getLayeringSuggestions("experimental"),
  ]);
  const suggestions = [...safe, ...contrast, ...experimental];
  const owned = collection.filter((item) => item.status === "owned").map((item) => item.fragrance);
  return <LayeringLab initialA={a} owned={owned} suggestions={suggestions} />;
}
