import { FragrancePageRoute } from "@/features/fragrance/fragrance-route";
import { isAtelierEnabled } from "@/lib/atelier-flag";

export default async function FragrancePage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { id } = await params;
  const query = await searchParams;
  return <FragrancePageRoute fragranceId={id} query={query} atelier={isAtelierEnabled()} />;
}
