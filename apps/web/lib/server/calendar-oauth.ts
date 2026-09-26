// Server-only by way of api-client, which refuses to load in the browser.
import { ApiError } from "@/lib/server/api-client";
import { CALENDAR_NOTICES } from "@/lib/calendar";
import type { CalendarProviderName } from "@/types/api";

/**
 * Shared pieces of the calendar OAuth route handlers.
 *
 * Provider errors are never shown verbatim: every outcome is mapped to one of
 * the notice codes the Settings page knows how to explain.
 */

export function parseProvider(value: string): CalendarProviderName | null {
  return value === "google" || value === "microsoft" ? value : null;
}

export function noticeCodeFor(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.kind === "unauthorized") throw error;
    if (error.code in CALENDAR_NOTICES) return error.code;
    if (error.kind === "unavailable") return "unavailable";
  }
  return "authorization_failed";
}

export function settingsRedirect(request: Request, parameter: string, value: string): Response {
  const target = new URL("/settings", request.url);
  target.searchParams.set(parameter, value);
  target.hash = "calendar";
  return Response.redirect(target, 303);
}
