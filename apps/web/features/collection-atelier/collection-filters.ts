import { ACCORD_KEYS, accordFor, type AccordKey } from "@/lib/accord";
import type { CollectionItem, OwnershipType } from "@/types/api";

export type Segment = "shelf" | "wishlist" | "blends";
export type SortKey = "rating" | "name" | "house" | "left";

export const SORT_LABELS: Record<SortKey, string> = {
  rating: "Highest rated",
  name: "A to Z",
  house: "House",
  left: "Least left",
};

export type CollectionFilters = {
  query: string;
  accords: AccordKey[];
  finished: boolean;
  formats: OwnershipType[];
  sort: SortKey;
};

export const DEFAULT_FILTERS: CollectionFilters = { query: "", accords: [], finished: false, formats: [], sort: "rating" };

export function isRetired(item: Pick<CollectionItem, "status">): boolean {
  return item.status === "finished" || item.status === "sold";
}

/** Items for a segment before filtering: owned on the shelf (retired only under Finished), wishlist on Wishlist. */
export function segmentItems(items: readonly CollectionItem[], segment: Segment, finished = false): CollectionItem[] {
  if (segment === "wishlist") return items.filter((item) => item.status === "wishlist");
  if (segment === "shelf") return items.filter((item) => (finished ? isRetired(item) : item.status === "owned"));
  return [];
}

/** Share of the bottle left, or null when the sizes are not recorded. */
export function fractionLeft(item: Pick<CollectionItem, "remaining_ml" | "bottle_size_ml">): number | null {
  if (item.remaining_ml === null || !item.bottle_size_ml) return null;
  return item.remaining_ml / item.bottle_size_ml;
}

/** "Nearly empty" at 10% or less, "Finished" when retired, otherwise nothing. */
export function statusLine(item: CollectionItem): string | null {
  if (isRetired(item)) return "Finished";
  const left = fractionLeft(item);
  return left !== null && left <= 0.1 ? "Nearly empty" : null;
}

/** Accord families present on the shelf, in the canonical order. */
export function accordsPresent(items: readonly CollectionItem[]): AccordKey[] {
  const present = new Set(items.map((item) => accordFor(item.fragrance)));
  return ACCORD_KEYS.filter((key) => key !== "neutral" && present.has(key));
}

function compareSort(sort: SortKey) {
  return (a: CollectionItem, b: CollectionItem): number => {
    if (sort === "name") return a.fragrance.name.localeCompare(b.fragrance.name);
    if (sort === "house") return a.fragrance.brand.name.localeCompare(b.fragrance.brand.name) || a.fragrance.name.localeCompare(b.fragrance.name);
    if (sort === "left") {
      const left = (item: CollectionItem) => fractionLeft(item) ?? Number.POSITIVE_INFINITY;
      return left(a) - left(b) || a.fragrance.name.localeCompare(b.fragrance.name);
    }
    // Highest rated; unrated items sort last rather than as zero.
    return (b.user_rating ?? -1) - (a.user_rating ?? -1) || a.fragrance.name.localeCompare(b.fragrance.name);
  };
}

/** Client-side search (name and house), accord chips (any of), format, then sort. */
export function applyFilters(items: readonly CollectionItem[], filters: CollectionFilters): CollectionItem[] {
  const needle = filters.query.trim().toLowerCase();
  return items
    .filter((item) => {
      const label = `${item.fragrance.brand.name} ${item.fragrance.name}`.toLowerCase();
      if (needle && !label.includes(needle)) return false;
      if (filters.accords.length > 0 && !filters.accords.includes(accordFor(item.fragrance))) return false;
      if (filters.formats.length > 0 && !filters.formats.includes(item.ownership_type)) return false;
      return true;
    })
    .sort(compareSort(filters.sort));
}
