import { AtelierError, AtelierUnavailable } from "@/components/atelier/states";
import { RetryButton } from "@/features/fragrance/retry-button";
import { ApiError } from "@/lib/server/api-client";
import { getCollection, getInsights } from "@/lib/server/queries";
import type { CollectionInsights, CollectionItem } from "@/types/api";

import { TasteView } from "./taste-view";

/** Insights joined with the collection, so entries can show their plates. */
export async function TasteBoundary() {
  let insights: CollectionInsights;
  let collection: CollectionItem[];
  try {
    [insights, collection] = await Promise.all([
      getInsights(),
      getCollection().catch((error: unknown) => { if (error instanceof ApiError && error.kind === "unauthorized") throw error; return [] as CollectionItem[]; }),
    ]);
  } catch (error) {
    if (error instanceof ApiError && error.kind === "unavailable") return <AtelierUnavailable retry={<RetryButton />} />;
    if (error instanceof ApiError) return <div className="at-page"><AtelierError title="Your taste did not load" message={error.message} retry={<RetryButton />} /></div>;
    throw error;
  }
  return <TasteView insights={insights} collection={collection} />;
}
