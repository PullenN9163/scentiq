import type { CalendarEvent, CalendarProviderName } from "@/types/api";

/** Calendar helpers shared by the server pages and the client views. */

export const PROVIDER_LABELS: Record<CalendarProviderName, string> = {
  google: "Google Calendar",
  microsoft: "Outlook Calendar",
};

/** What a screen showing events has to work with. */
export type CalendarResult =
  | { status: "ok"; events: CalendarEvent[]; needsReconnect: boolean }
  | { status: "not_connected" }
  | { status: "unavailable" };

function zonedParts(instant: Date, timeZone: string): Record<string, number> {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(instant);
  const values: Record<string, number> = {};
  for (const part of parts) {
    if (part.type !== "literal") values[part.type] = Number(part.value);
  }
  return values;
}

function offsetMs(instant: Date, timeZone: string): number {
  const parts = zonedParts(instant, timeZone);
  const asUtc = Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, parts.second);
  return asUtc - Math.floor(instant.getTime() / 1000) * 1000;
}

export function safeTimeZone(timeZone: string | null | undefined): string {
  if (!timeZone) return "UTC";
  try {
    new Intl.DateTimeFormat("en-US", { timeZone });
    return timeZone;
  } catch {
    return "UTC";
  }
}

/** The member's local calendar date for an instant, as `YYYY-MM-DD`. */
export function localDate(instant: Date, timeZone: string): string {
  const parts = zonedParts(instant, timeZone);
  return `${parts.year}-${String(parts.month).padStart(2, "0")}-${String(parts.day).padStart(2, "0")}`;
}

/** The UTC instants bounding a local calendar date, DST included. */
export function dayBounds(date: string, timeZone: string): { start: Date; end: Date } {
  const [year, month, day] = date.split("-").map(Number);
  const startOf = (y: number, m: number, d: number) => {
    const guess = Date.UTC(y, m - 1, d);
    const first = guess - offsetMs(new Date(guess), timeZone);
    // Re-read the offset at the candidate instant in case a DST change sits between.
    return new Date(guess - offsetMs(new Date(first), timeZone));
  };
  return { start: startOf(year, month, day), end: startOf(year, month, day + 1) };
}

/**
 * Whether an event falls on a local date.
 *
 * All-day events are dates, not instants, so they are compared by date; timed
 * events are compared against the local day's bounds.
 */
export function occursOn(event: CalendarEvent, date: string, timeZone: string): boolean {
  if (event.is_all_day) {
    const first = event.starts_at.slice(0, 10);
    const afterLast = event.ends_at.slice(0, 10);
    return first === date || (first < date && date < afterLast);
  }
  const { start, end } = dayBounds(date, timeZone);
  const startsAt = new Date(event.starts_at).getTime();
  const endsAt = new Date(event.ends_at).getTime();
  return startsAt < end.getTime() && (endsAt > start.getTime() || startsAt >= start.getTime());
}

/** Narrow a calendar result to the events on one local date. */
export function eventsOn(result: CalendarResult, date: string, timeZone: string): CalendarResult {
  if (result.status !== "ok") return result;
  return { ...result, events: result.events.filter((event) => occursOn(event, date, timeZone)) };
}

export function formatEventTime(event: CalendarEvent, timeZone: string): string {
  if (event.is_all_day) return "All day";
  return new Date(event.starts_at).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone,
  });
}

const OCCASION_LABELS: Record<CalendarEvent["occasion"], string> = {
  work: "Work",
  casual: "Casual",
  date: "Date",
  dinner: "Dinner",
  party: "Party",
  formal: "Formal",
  gym: "Gym",
  travel: "Travel",
  other: "Event",
};

export function occasionLabel(occasion: CalendarEvent["occasion"]): string {
  return OCCASION_LABELS[occasion];
}

/** Settings-page notices for the OAuth round trip, keyed by query value. */
export const CALENDAR_NOTICES: Record<string, { tone: "success" | "error"; message: string }> = {
  connected: { tone: "success", message: "Calendar connected. Your events are syncing." },
  access_denied: { tone: "error", message: "Calendar access was not granted, so nothing was connected." },
  invalid_oauth_state: {
    tone: "error",
    message: "That connection request expired. Please try connecting again.",
  },
  calendar_scope_not_granted: {
    tone: "error",
    message: "Calendar access wasn't allowed. Connect again and tick the calendar permission.",
  },
  authorization_failed: {
    tone: "error",
    message: "The calendar provider rejected the connection. Please try again.",
  },
  unavailable: {
    tone: "error",
    message: "The calendar service is unavailable right now. Please try again shortly.",
  },
};
