import type {
  CollectionInsights,
  DiscoveryResult,
  FragranceDetail,
  FragranceSummary,
  LayeringSuggestion,
} from "@/types/api";

export function fragranceSummary(
  overrides: Partial<FragranceSummary> = {},
): FragranceSummary {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    name: "Source Scent",
    concentration: null,
    release_year: 2020,
    image_blob_path: null,
    image_url: null,
    gender: "unisex",
    olfactory_family: "Woody",
    rating_average: 4.2,
    rating_count: 10,
    top_accords: ["Woody"],
    longevity_score: 7,
    projection_level: "moderate",
    brand: {
      id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      name: "Source House",
      slug: "source-house",
      country: null,
    },
    is_custom: false,
    ...overrides,
  };
}

export function fragranceDetail(overrides: Partial<FragranceDetail> = {}): FragranceDetail {
  return {
    ...fragranceSummary(),
    description: null,
    product_line: null,
    notes: [],
    accords: [],
    seasons: [{ season: "fall", weight: 1 }],
    occasions: [],
    perfumers: [],
    community: {
      longevity_average: 3.5,
      longevity_votes: 10,
      sillage_average: 2.5,
      sillage_votes: 10,
      price_value_average: 3.8,
      price_value_votes: 10,
      have_count: 1,
      had_count: 0,
      want_count: 2,
      perceived_female: 0,
      perceived_female_leaning: 0,
      perceived_unisex: 10,
      perceived_male_leaning: 0,
      perceived_male: 0,
      day_votes: 8,
      night_votes: 2,
      voters: 10,
      captured_at: null,
    },
    similar: [],
    sources: [],
    ...overrides,
  };
}

export function collectionInsights(
  overrides: Partial<CollectionInsights> = {},
): CollectionInsights {
  return {
    total_items: 2,
    owned_items: 2,
    wishlist_items: 0,
    retired_items: 0,
    custom_items: 0,
    total_purchase_value: null,
    priced_items: 0,
    average_rating: 4.2,
    rated_items: 1,
    total_wears: 0,
    wears_last_30_days: 0,
    distinct_fragrances_worn: 0,
    most_worn: [],
    accords: [{ label: "Woody", count: 2, share: 1 }],
    seasons: [],
    occasions: [],
    ownership_types: [{ label: "bottle", count: 2 }],
    unclassified_items: 0,
    ...overrides,
  };
}

export function discoveryResult(
  overrides: Partial<DiscoveryResult> = {},
): DiscoveryResult {
  return {
    fragrance: fragranceSummary(),
    taste_match: 0.8,
    collection_expansion: 0.7,
    redundancy_risk: 0.2,
    score: 0.75,
    ...overrides,
  };
}

export function layeringSuggestion(
  overrides: Partial<LayeringSuggestion> = {},
): LayeringSuggestion {
  const first = fragranceSummary();
  const second = fragranceSummary({
    id: "22222222-2222-4222-8222-222222222222",
    name: "Second Source Scent",
  });
  return {
    first,
    second,
    mode: "safe",
    score: 0.84,
    shared_notes: ["Cedar"],
    complementary_accords: ["Woody", "Citrus"],
    season_overlap: 0.75,
    ...overrides,
  };
}
