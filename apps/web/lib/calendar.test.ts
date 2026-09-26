import { describe, expect, it } from "vitest";

import { dayBounds, formatEventTime, localDate, occursOn, safeTimeZone } from "@/lib/calendar";
import type { CalendarEvent } from "@/types/api";

function event(overrides: Partial<CalendarEvent>): CalendarEvent {
  return {
    id: "e1",
    title: "Team sync",
    starts_at: "2026-09-26T13:00:00Z",
    ends_at: "2026-09-26T14:00:00Z",
    is_all_day: false,
    location_label: null,
    occasion: "work",
    formality: "smart",
    is_hidden: false,
    calendar_name: "Personal",
    provider: "google",
    ...overrides,
  };
}

describe("calendar dates", () => {
  it("finds the local date and its bounds", () => {
    const instant = new Date("2026-09-27T02:00:00Z");
    expect(localDate(instant, "America/New_York")).toBe("2026-09-26");
    expect(localDate(instant, "Europe/London")).toBe("2026-09-27");

    const { start, end } = dayBounds("2026-09-26", "America/New_York");
    expect(start.toISOString()).toBe("2026-09-26T04:00:00.000Z");
    expect(end.toISOString()).toBe("2026-09-27T04:00:00.000Z");
  });

  it("handles a day with a daylight-saving change", () => {
    const { start, end } = dayBounds("2026-10-25", "Europe/London");
    expect(start.toISOString()).toBe("2026-10-24T23:00:00.000Z");
    expect(end.toISOString()).toBe("2026-10-26T00:00:00.000Z");
  });

  it("falls back to UTC for an unknown zone", () => {
    expect(safeTimeZone("Not/AZone")).toBe("UTC");
    expect(safeTimeZone(null)).toBe("UTC");
    expect(safeTimeZone("Europe/Paris")).toBe("Europe/Paris");
  });
});

describe("occursOn", () => {
  it("places timed events on the member's local day", () => {
    const late = event({ starts_at: "2026-09-27T01:00:00Z", ends_at: "2026-09-27T02:00:00Z" });
    expect(occursOn(late, "2026-09-26", "America/New_York")).toBe(true);
    expect(occursOn(late, "2026-09-27", "America/New_York")).toBe(false);
    expect(occursOn(late, "2026-09-27", "Europe/London")).toBe(true);
  });

  it("compares all-day events by date whatever the zone", () => {
    const allDay = event({
      is_all_day: true,
      starts_at: "2026-09-27T00:00:00Z",
      ends_at: "2026-09-29T00:00:00Z",
    });
    expect(occursOn(allDay, "2026-09-26", "America/New_York")).toBe(false);
    expect(occursOn(allDay, "2026-09-27", "America/New_York")).toBe(true);
    expect(occursOn(allDay, "2026-09-28", "Pacific/Auckland")).toBe(true);
    expect(occursOn(allDay, "2026-09-29", "Pacific/Auckland")).toBe(false);
  });

  it("formats times in the member's zone", () => {
    expect(formatEventTime(event({}), "America/New_York")).toBe("09:00");
    expect(formatEventTime(event({ is_all_day: true }), "UTC")).toBe("All day");
  });
});
