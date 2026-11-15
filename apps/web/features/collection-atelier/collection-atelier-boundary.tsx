import { AtelierError, AtelierUnavailable } from "@/components/atelier/states";
import { ApiError } from "@/lib/server/api-client";
import { getLayeringIntelligence } from "@/lib/server/layering-actions";
import { getCollection, getInsightsSummary, searchFragrances } from "@/lib/server/queries";
import type { CollectionItem, FragranceSummary, WeightedSlice } from "@/types/api";
import type { SavedLayeringStack } from "@/types/layering";

import { CollectionAtelier } from "./collection-atelier";
import type { Segment } from "./collection-filters";

/** Supplementary reads: a failure hides their section rather than the page. */
async function optional<T>(read: Promise<T>): Promise<T | null> {
  try {
    return await read;
  } catch (error) {
    if (error instanceof ApiError && error.kind === "unauthorized") throw error;
    return null;
  }
}

export async function CollectionAtelierBoundary({ segment }: { segment: Segment }) {
  let items: CollectionItem[];
  let catalog: FragranceSummary[];
  let accords: WeightedSlice[] | null;
  let saved: SavedLayeringStack[] | null;
  try {
    const [collection, catalogPage, insights, intelligence] = await Promise.all([
      getCollection(),
      searchFragrances(undefined, 50),
      optional(getInsightsSummary()),
      optional(getLayeringIntelligence()),
    ]);
    items = collection;
    catalog = catalogPage;
    accords = insights?.accords ?? null;
    saved = intelligence?.saved ?? null;
  } catch (error) {
    if (error instanceof ApiError && error.kind === "unavailable") return <AtelierUnavailable />;
    if (error instanceof ApiError) return <div className="at-page"><AtelierError title="Your collection did not load" message={error.message} /></div>;
    throw error;
  }
  return <CollectionAtelier items={items} catalog={catalog} tasteAccords={accords} saved={saved} initialSegment={segment} />;
}
