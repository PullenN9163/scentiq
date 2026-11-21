import { ACCORD_KEYS, ACCORD_LABELS } from "@/lib/accord";
import type { DiscoveryResult } from "@/types/api";

export type DiscoverMode = "balance" | "taste" | "explore" | "seasonal";
export type DiscoverFilters = { mode: DiscoverMode; season: string; family: string; gender: string; minimum_value: string };

export const MODES: { value: DiscoverMode; label: string; shortLabel: string }[] = [
  { value: "balance", label: "Balance my shelf", shortLabel: "Balance" },
  { value: "taste", label: "More of what I love", shortLabel: "Love" },
  { value: "explore", label: "Explore something new", shortLabel: "Explore" },
  { value: "seasonal", label: "For the season", shortLabel: "Season" },
];

export const FAMILY_CHOICES = ACCORD_KEYS.filter((key) => key !== "neutral").map((key) => ACCORD_LABELS[key]);
export const SEASON_CHOICES: [string, string][] = [["spring", "Spring"], ["summer", "Summer"], ["fall", "Fall"], ["winter", "Winter"]];
export const GENDER_CHOICES: [string, string][] = [["female", "Female"], ["male", "Male"], ["unisex", "Unisex"]];
export const VALUE_CHOICES: [string, string][] = [["3", "Value 3+"], ["4", "Value 4+"]];

export function toMode(value: string | null | undefined): DiscoverMode {
  return MODES.some((mode) => mode.value === value) ? (value as DiscoverMode) : "balance";
}

/** How many of the sheet filters are set (mode is not a filter). */
export function filterCount(filters: DiscoverFilters): number {
  return [filters.family, filters.season, filters.gender, filters.minimum_value].filter(Boolean).length;
}

/** The URL the existing page reads: q, mode, family, season, gender, minimum_value. */
export function discoverHref(query: string, filters: DiscoverFilters): string {
  const params = new URLSearchParams();
  if (query.trim()) params.set("q", query.trim().slice(0, 120));
  if (filters.mode !== "balance") params.set("mode", filters.mode);
  if (filters.family) params.set("family", filters.family);
  if (filters.season) params.set("season", filters.season);
  if (filters.gender) params.set("gender", filters.gender);
  if (filters.minimum_value) params.set("minimum_value", filters.minimum_value);
  return `/discover${params.size ? `?${params}` : ""}`;
}

/**
 * The reason line for a result: its first reason, or a sentence built from
 * taste match and collection expansion, in words, never numbers.
 */
export function reasonFor(result: Pick<DiscoveryResult, "reasons" | "taste_match" | "collection_expansion">): string {
  const first = result.reasons?.find((reason) => reason.trim());
  if (first) return /[.!?]$/.test(first.trim()) ? first.trim() : `${first.trim()}.`;
  const taste = result.taste_match >= 0.7 ? "Close to what you love" : result.taste_match >= 0.4 ? "Near your usual taste" : "A step away from your usual taste";
  const expansion = result.collection_expansion >= 0.6 ? "adds something new to your shelf" : result.collection_expansion >= 0.3 ? "rounds out your shelf" : "sits close to what you already own";
  return `${taste}, and it ${expansion}.`;
}

/** Scores in words, for the fragrance sheet's "Why it suits you" line. */
export function suitsWords(result: Pick<DiscoveryResult, "taste_match" | "collection_expansion">): string[] {
  const words: string[] = [];
  if (result.taste_match >= 0.6) words.push("Fits your taste");
  if (result.collection_expansion >= 0.5) words.push("Adds something new");
  return words;
}

/** Fragrance detail link that keeps the Discover back link. */
export function detailHref(fragranceId: string, query?: string): string {
  const parameters = new URLSearchParams({ from: "discover" });
  if (query?.trim()) parameters.set("q", query.trim());
  return `/collection/${fragranceId}?${parameters.toString()}`;
}
