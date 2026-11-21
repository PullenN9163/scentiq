import { FragranceSheetRoute } from "@/features/fragrance/fragrance-route";
import { isAtelierEnabled } from "@/lib/atelier-flag";

/** Soft navigation to /collection/[id] opens the fragrance sheet over the current page. */
export default async function FragranceSheetPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { id } = await params;
  const query = await searchParams;
  return <FragranceSheetRoute fragranceId={id} query={query} atelier={isAtelierEnabled()} />;
}
