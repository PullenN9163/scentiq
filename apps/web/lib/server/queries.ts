import "server-only";

import { ApiError, apiClient } from "@/lib/server/api-client";
import type { CalendarResult } from "@/lib/calendar";
import type { WeatherResult } from "@/lib/weather";
import type {
  CalendarConnection,
  CalendarEvent,
  CalendarProviderStatus,
  CollectionInsights,
  CollectionItem,
  DiscoveryResult,
  FragranceDetail,
  FragranceSummary,
  Me,
  LayeringMode,
  LayeringSuggestion,
  WearLogEntry,
  WeatherForecast,
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

/**
 * The forecast, or why there isn't one.
 *
 * Weather is supplementary: a missing location or an unreachable provider is
 * reported as a state for the page to show, never thrown, so it cannot take
 * down the screen it sits on. Only an authentication failure propagates.
 */
export async function getWeather(): Promise<WeatherResult> {
  try {
    const forecast = await apiClient.get<WeatherForecast>("/api/v1/weather/forecast");
    return { status: "ok", forecast };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.kind === "unauthorized") throw error;
      if (error.code === "location_required") return { status: "location_required" };
      if (error.code === "location_unresolved") return { status: "location_unresolved" };
    }
    return { status: "unavailable" };
  }
}

// --- calendar ------------------------------------------------------------

export function getCalendarProviders(): Promise<CalendarProviderStatus[]> {
  return apiClient.get<CalendarProviderStatus[]>("/api/v1/calendar/providers");
}

export function getCalendarConnections(): Promise<CalendarConnection[]> {
  return apiClient.get<CalendarConnection[]>("/api/v1/calendar/connections");
}

export function getCalendarEvents(start: Date, end: Date): Promise<CalendarEvent[]> {
  const parameters = new URLSearchParams({ start: start.toISOString(), end: end.toISOString() });
  return apiClient.get<CalendarEvent[]>(`/api/v1/calendar/events?${parameters.toString()}`);
}

const DAY_MS = 24 * 60 * 60 * 1000;

/**
 * Events from a day before to two days after `now`, or why there are none.
 *
 * The window covers "today" in every timezone, so this can run alongside the
 * profile read that supplies the member's zone; `eventsOn` then narrows it.
 * Like the forecast, calendar trouble is a state for the page rather than an
 * error, so a provider outage cannot take down the screen.
 */
export async function getCalendarAround(now = new Date()): Promise<CalendarResult> {
  try {
    const connections = await getCalendarConnections();
    if (connections.length === 0) return { status: "not_connected" };
    const events = await getCalendarEvents(
      new Date(now.getTime() - DAY_MS),
      new Date(now.getTime() + 2 * DAY_MS),
    );
    return {
      status: "ok",
      events,
      needsReconnect: connections.some((connection) => connection.status === "reauth_required"),
    };
  } catch (error) {
    if (error instanceof ApiError && error.kind === "unauthorized") throw error;
    return { status: "unavailable" };
  }
}
