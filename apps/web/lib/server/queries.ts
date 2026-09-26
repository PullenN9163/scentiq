import "server-only";

import { apiClient } from "@/lib/server/api-client";
import type {
  CollectionInsights,
  CollectionItem,
  DiscoveryResult,
  FragranceDetail,
  FragranceSummary,
  Me,
  LayeringMode,
  LayeringSuggestion,
  WearLogEntry,
} from "@/types/api";

/**
 * Reads used by Server Components.
 *
 * None of these are cached: every response is specific to the signed-in member.
 * A Server Action revalidates the affected route, which re-runs the read.
 */

export function getMe(): Promise<Me> {
  return apiClient.get<Me>("/api/v1/me");
}

export function getCollection(): Promise<CollectionItem[]> {
  return apiClient.get<CollectionItem[]>("/api/v1/collection");
}

export function getInsights(): Promise<CollectionInsights> {
  return apiClient.get<CollectionInsights>("/api/v1/insights/collection");
}

export function getFragrance(fragranceId: string): Promise<FragranceDetail> {
  return apiClient.get<FragranceDetail>(`/api/v1/fragrances/${fragranceId}`);
}

export function searchFragrances(
  query?: string,
  limit = 25,
  offset = 0,
): Promise<FragranceSummary[]> {
  const parameters = new URLSearchParams();
  if (query && query.trim()) {
    parameters.set("q", query.trim());
  }
  parameters.set("limit", String(limit));
  parameters.set("offset", String(offset));
  parameters.set("sort", query?.trim() ? "relevance" : "popular");
  return apiClient.get<FragranceSummary[]>(`/api/v1/fragrances?${parameters.toString()}`);
}

export function getDiscover(options: {
  gender?: string;
  family?: string;
  season?: string;
  minimumValue?: string;
} = {}): Promise<DiscoveryResult[]> {
  const parameters = new URLSearchParams();
  if (options.gender) parameters.set("gender", options.gender);
  if (options.family) parameters.set("family", options.family);
  if (options.season) parameters.set("season", options.season);
  if (options.minimumValue) parameters.set("minimum_value", options.minimumValue);
  return apiClient.get<DiscoveryResult[]>(`/api/v1/discover?${parameters.toString()}`);
}

export function getLayeringSuggestions(
  mode: LayeringMode = "safe",
): Promise<LayeringSuggestion[]> {
  return apiClient.get<LayeringSuggestion[]>(
    `/api/v1/layering/suggestions?mode=${encodeURIComponent(mode)}`,
  );
}

export function getWearLogs(
  options: { collectionItemId?: string; fragranceId?: string; limit?: number } = {},
): Promise<WearLogEntry[]> {
  const parameters = new URLSearchParams();
  if (options.collectionItemId) {
    parameters.set("collection_item_id", options.collectionItemId);
  }
  if (options.fragranceId) {
    parameters.set("fragrance_id", options.fragranceId);
  }
  parameters.set("limit", String(options.limit ?? 50));
  return apiClient.get<WearLogEntry[]>(`/api/v1/wear-logs?${parameters.toString()}`);
}
