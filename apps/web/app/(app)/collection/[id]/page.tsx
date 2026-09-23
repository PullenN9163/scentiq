import { notFound } from "next/navigation";
import { FragranceDetail } from "@/features/collection/fragrance-detail";
import { fragrances, getDemoFragranceById } from "@/lib/demo";

export function generateStaticParams() { return fragrances.map(({ id }) => ({ id })); }
export default async function FragrancePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!getDemoFragranceById(id)) notFound();
  return <FragranceDetail fragranceId={id} />;
}
