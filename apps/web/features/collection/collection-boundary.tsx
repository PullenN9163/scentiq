import { ErrorState, UnavailableState } from "@/components/shared/states";
import { CollectionView } from "@/features/collection/collection-view";
import { ApiError } from "@/lib/server/api-client";
import { getCollection, searchFragrances } from "@/lib/server/queries";
import type { CollectionItem, FragranceSummary } from "@/types/api";

/**
 * Fetches the collection and the catalog the add dialog offers.
 *
 * Only the awaits sit inside the try. Constructing the view there would suggest
 * render errors are caught too, which they are not — those belong to an error
 * boundary.
 */
export async function CollectionBoundary() {
  let items: CollectionItem[];
  let catalog: FragranceSummary[];

  try {
    [items, catalog] = await Promise.all([getCollection(), searchFragrances(undefined, 50)]);
  } catch (error) {
    if (error instanceof ApiError && error.kind === "unavailable") {
      return <UnavailableState />;
    }
    if (error instanceof ApiError) {
      return <ErrorState message={error.message} />;
    }
    throw error;
  }

  return <CollectionView items={items} catalog={catalog} />;
}
