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

/**
 * Back to Settings, as a relative redirect the browser resolves against the
 * public URL it is on.
 *
 * `request.url` can't be used as the base: the standalone server builds it
 * from its own bind address (`HOSTNAME=0.0.0.0`, port 3000), so an absolute
 * redirect from it sends the member to `localhost:3000` instead of the app.
 */
export function settingsRedirect(parameter: string, value: string): Response {
  const query = new URLSearchParams({ [parameter]: value });
  return new Response(null, {
    status: 303,
    headers: { Location: `/settings?${query.toString()}#calendar` },
  });
}
