import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ErrorState, LoadingState, UnavailableState } from "@/components/shared/states";
import { FragranceDetailView } from "@/features/collection/fragrance-detail-view";
import { ApiError } from "@/lib/server/api-client";
import { getCollection, getFragrance, getWearLogs } from "@/lib/server/queries";
import type { CollectionItem, FragranceDetail, WearLogEntry } from "@/types/api";

async function FragranceDetailBoundary({ fragranceId }: { fragranceId: string }) {
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

  return <FragranceDetailView fragrance={fragrance} ownedItem={ownedItem} wears={wears} />;
}

export default async function FragrancePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense fallback={<LoadingState rows={4} label="Loading fragrance" />}>
      <FragranceDetailBoundary fragranceId={id} />
    </Suspense>
  );
}
