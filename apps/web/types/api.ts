/**
 * Hand-maintained mirrors of the ScentIQ API contract.
 *
 * `types/api.generated.ts` is produced from `apps/api/openapi.json` by
 * `pnpm contracts` and is the source of truth; CI fails when the two drift.
 * These aliases exist so application code reads well and does not index deeply
 * into the generated tree.
 */

export type Season = "spring" | "summer" | "fall" | "winter";
export type Projection = "intimate" | "moderate" | "strong";
export type Occasion =
  | "work"
  | "casual"
  | "date"
  | "dinner"
  | "party"
  | "formal"
  | "gym"
  | "travel"
  | "other";
export type OwnershipType = "bottle" | "decant" | "sample";
export type CollectionStatus = "owned" | "wishlist" | "finished" | "sold";
export type NoteStage = "top" | "middle" | "base" | "general";
export type LifecycleState = "active" | "deletion_pending";

export interface Brand {
  id: string;
  name: string;
  slug: string;
  country: string | null;
}

export interface FragranceSummary {
  id: string;
  name: string;
  concentration: string | null;
  release_year: number | null;
  image_blob_path: string | null;
  image_url: string | null;
  gender: "male" | "female" | "unisex" | null;
  olfactory_family: string | null;
  rating_average: number | null;
  rating_count: number | null;
  top_accords: string[];
  longevity_score: number | null;
  projection_level: Projection | null;
  brand: Brand;
  is_custom: boolean;
}

export interface FragranceNote {
  id: string;
  name: string;
  slug: string;
  stage: NoteStage;
  weight: number | null;
}

export interface FragranceAccord {
  id: string;
  name: string;
  slug: string;
  weight: number;
}

export interface FragranceDetail extends FragranceSummary {
  description: string | null;
  product_line: string | null;
  notes: FragranceNote[];
  accords: FragranceAccord[];
  seasons: { season: Season; weight: number }[];
  occasions: { occasion: Occasion; weight: number }[];
  perfumers: { id: string; name: string; slug: string }[];
  community: {
    longevity_average: number | null;
    longevity_votes: number | null;
    sillage_average: number | null;
    sillage_votes: number | null;
    price_value_average: number | null;
    price_value_votes: number | null;
    have_count: number | null;
    had_count: number | null;
    want_count: number | null;
    perceived_female: number | null;
    perceived_female_leaning: number | null;
    perceived_unisex: number | null;
    perceived_male_leaning: number | null;
    perceived_male: number | null;
    day_votes: number | null;
    night_votes: number | null;
    voters: number | null;
    captured_at: string | null;
  } | null;
  similar: FragranceSummary[];
  sources: { source: string; url: string | null }[];
}

export interface DiscoveryResult {
  fragrance: FragranceSummary;
  taste_match: number;
  collection_expansion: number;
  redundancy_risk: number;
  score: number;
}

export type LayeringMode = "safe" | "contrast" | "experimental";

export interface LayeringSuggestion {
  first: FragranceSummary;
  second: FragranceSummary;
  mode: LayeringMode;
  score: number;
  shared_notes: string[];
  complementary_accords: string[];
  season_overlap: number;
}

export interface CollectionItem {
  id: string;
  ownership_type: OwnershipType;
  bottle_size_ml: number | null;
  remaining_ml: number | null;
  /** Decimal string, e.g. "129.50". */
  purchase_price: string | null;
  purchase_date: string | null;
  user_rating: number | null;
  custom_longevity: number | null;
  custom_projection: Projection | null;
  status: CollectionStatus;
  fragrance: FragranceSummary;
}

export interface WearLogEntry {
  id: string;
  collection_item_id: string;
  fragrance_id: string;
  fragrance_name: string;
  brand_name: string;
  worn_at: string;
  sprays: number | null;
  occasion: Occasion | null;
  setting: string | null;
  notes: string | null;
}

export interface Preferences {
  location: string | null;
  preferred_season: Season | null;
  preferred_occasion: Occasion | null;
  preferred_projection: Projection | null;
  preferred_longevity: number | null;
  maximum_sprays: number | null;
}

export interface Me {
  id: string;
  email: string;
  display_name: string;
  lifecycle_state: LifecycleState;
  created_at: string;
  preferences: Preferences;
}

export interface WeightedSlice {
  label: string;
  count: number;
  share: number;
}

export interface CountSlice {
  label: string;
  count: number;
}

export interface MostWornEntry {
  collection_item_id: string;
  fragrance_id: string;
  fragrance_name: string;
  brand_name: string;
  wear_count: number;
}

export interface CollectionInsights {
  total_items: number;
  owned_items: number;
  wishlist_items: number;
  retired_items: number;
  custom_items: number;
  /** Decimal string, or null when nothing is priced. */
  total_purchase_value: string | null;
  priced_items: number;
  average_rating: number | null;
  rated_items: number;
  total_wears: number;
  wears_last_30_days: number;
  distinct_fragrances_worn: number;
  most_worn: MostWornEntry[];
  accords: WeightedSlice[];
  seasons: WeightedSlice[];
  occasions: WeightedSlice[];
  ownership_types: CountSlice[];
  /** Items with no shared-catalog classification behind the breakdowns. */
  unclassified_items: number;
}

export interface DeletionAccepted {
  lifecycle_state: LifecycleState;
  deletion_requested_at: string;
}
