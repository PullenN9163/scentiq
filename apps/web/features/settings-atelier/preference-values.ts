import type { Preferences } from "@/types/api";

/** Every field the existing preferences form posts. */
export const PREFERENCE_FIELDS = [
  "liked_notes", "disliked_notes", "liked_accords", "disliked_accords", "liked_families", "disliked_families",
  "excluded_fragrance_ids", "variety_preference", "calendar_ai_titles_enabled", "location", "temperature_unit",
  "preferred_season", "preferred_occasion", "preferred_projection", "preferred_longevity", "maximum_sprays",
] as const;

export type PreferenceField = (typeof PREFERENCE_FIELDS)[number];

/**
 * The saved preferences in the exact format the existing form posts. Saving
 * replaces the whole set, so each section sends every other field unchanged.
 * `calendar_ai_titles_enabled` is a checkbox: present as "on" only when true.
 */
export function preferenceValues(preferences: Preferences): Record<PreferenceField, string | null> {
  return {
    liked_notes: (preferences.liked_notes ?? []).join(", "),
    disliked_notes: (preferences.disliked_notes ?? []).join(", "),
    liked_accords: (preferences.liked_accords ?? []).join(", "),
    disliked_accords: (preferences.disliked_accords ?? []).join(", "),
    liked_families: (preferences.liked_families ?? []).join(", "),
    disliked_families: (preferences.disliked_families ?? []).join(", "),
    excluded_fragrance_ids: (preferences.excluded_fragrance_ids ?? []).join(","),
    variety_preference: preferences.variety_preference ?? "balanced",
    calendar_ai_titles_enabled: preferences.calendar_ai_titles_enabled ? "on" : null,
    location: preferences.location ?? "",
    temperature_unit: preferences.temperature_unit ?? "",
    preferred_season: preferences.preferred_season ?? "",
    preferred_occasion: preferences.preferred_occasion ?? "",
    preferred_projection: preferences.preferred_projection ?? "",
    preferred_longevity: preferences.preferred_longevity?.toString() ?? "",
    maximum_sprays: preferences.maximum_sprays?.toString() ?? "",
  };
}
