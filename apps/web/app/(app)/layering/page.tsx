import { LayeringLab } from "@/features/layering/layering-lab";
import { getLayeringPage } from "@/lib/server/queries";

export default async function LayeringPage({ searchParams }: { searchParams: Promise<{ a?: string }> }) {
  const { a } = await searchParams;
  const data = await getLayeringPage();
  const suggestions = Object.values(data.recommendations.payload.layering).flat();
  const owned = data.collection.filter((item) => item.status === "owned").map((item) => item.fragrance);
  return <LayeringLab initialA={a} owned={owned} suggestions={suggestions} />;
}
