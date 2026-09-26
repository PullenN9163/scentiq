import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ErrorState, LoadingState, UnavailableState } from "@/components/shared/states";
import { FragranceDetailView } from "@/features/collection/fragrance-detail-view";
import { ApiError } from "@/lib/server/api-client";
import { getCollection, getFragrance, getWearLogs } from "@/lib/server/queries";
import type { CollectionItem, FragranceDetail, WearLogEntry } from "@/types/api";

async function FragranceDetailBoundary({
  fragranceId,
  backHref,
  backLabel,
}: {
  fragranceId: string;
  backHref: string;
  backLabel: string;
}) {
  let fragrance: FragranceDetail;
  let ownedItem: CollectionItem | null;
  let wears: WearLogEntry[];

  try {
    const [detail, collection] = await Promise.all([getFragrance(fragranceId), getCollection()]);
    fragrance = detail;
    ownedItem = collection.find((item) => item.fragrance.id === fragranceId) ?? null;
    // Wears hang off the collection item, so there are none to fetch if the
    // fragrance is not owned.
    wears = ownedItem ? await getWearLogs({ collectionItemId: ownedItem.id, limit: 10 }) : [];
  } catch (error) {
    if (error instanceof ApiError && error.kind === "not_found") {
      notFound();
    }
    if (error instanceof ApiError && error.kind === "unavailable") {
      return <UnavailableState />;
    }
    if (error instanceof ApiError) {
      return <ErrorState message={error.message} />;
    }
    throw error;
  }

  return <FragranceDetailView fragrance={fragrance} ownedItem={ownedItem} wears={wears} backHref={backHref} backLabel={backLabel} />;
}

export default async function FragrancePage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { id } = await params;
  const query = await searchParams;
  const fromDiscover = query.from === "discover";
  const discoverParameters = new URLSearchParams();
  const discoverQuery = typeof query.q === "string" ? query.q.trim() : "";
  if (discoverQuery) discoverParameters.set("q", discoverQuery);
  const backHref = fromDiscover
    ? `/discover${discoverParameters.size ? `?${discoverParameters.toString()}` : ""}`
    : "/collection";
  return (
    <Suspense fallback={<LoadingState rows={4} label="Loading fragrance" />}>
      <FragranceDetailBoundary fragranceId={id} backHref={backHref} backLabel={fromDiscover ? "Back to Discover" : "Back to collection"} />
    </Suspense>
  );
}
