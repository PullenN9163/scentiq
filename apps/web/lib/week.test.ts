import { describe, expect, it } from "vitest";

import { buildWeek, contextFor, leadOccasion, nextDates, spanOf } from "@/lib/week";
import type { CalendarEvent, ForecastDay } from "@/types/api";

function event(overrides: Partial<CalendarEvent>): CalendarEvent {
  return {
    id: "e",
    title: "Event",
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

function forecast(date: string, high: number): ForecastDay {
  return {
    date,
    condition: "clear",
    high_celsius: high,
    low_celsius: null,
    precipitation_probability: null,
    humidity: null,
  };
}

describe("week planning", () => {
  it("lists the member's next seven local dates across a month end", () => {
    const dates = nextDates(new Date("2026-09-28T03:00:00Z"), "America/Los_Angeles");
    expect(dates).toEqual([
      "2026-09-27",
      "2026-09-28",
      "2026-09-29",
      "2026-09-30",
      "2026-10-01",
      "2026-10-02",
      "2026-10-03",
    ]);
    const span = spanOf(dates, "America/Los_Angeles");
    expect(span.start.toISOString()).toBe("2026-09-27T07:00:00.000Z");
    expect(span.end.toISOString()).toBe("2026-10-04T07:00:00.000Z");
  });

  it("matches forecasts and events to their days, each input optional", () => {
    const dates = ["2026-09-26", "2026-09-27"];
    const week = buildWeek(
      dates,
      { status: "ok", forecast: { location_label: "Leeds", timezone: "UTC", temperature_unit: "celsius", fetched_at: "", stale: false, days: [forecast("2026-09-27", 15)] } },
      { status: "ok", needsReconnect: false, events: [event({ id: "a" })] },
      "UTC",
    );
    expect(week[0].weather).toBeNull();
    expect(week[0].events.map((item) => item.id)).toEqual(["a"]);
    expect(week[1].weather?.high_celsius).toBe(15);
    expect(week[1].events).toEqual([]);

    const bare = buildWeek(dates, { status: "unavailable" }, { status: "not_connected" }, "UTC");
    expect(bare.every((day) => day.weather === null && day.events.length === 0)).toBe(true);
  });

  it("lets the most demanding occasion lead", () => {
    expect(leadOccasion([event({ occasion: "work" }), event({ occasion: "date" })])).toBe("date");
    expect(leadOccasion([event({ occasion: "other" })])).toBeNull();
    expect(leadOccasion([])).toBeNull();
  });

  it("derives ranking context from the day's plans and weather", () => {
    const dinner = event({
      occasion: "dinner",
      starts_at: "2026-09-26T23:00:00Z",
      ends_at: "2026-09-27T01:00:00Z",
    });
    const context = contextFor(
      { date: "2026-09-26", weather: forecast("2026-09-26", 24), events: [dinner] },
      "America/New_York",
    );
    expect(context).toEqual({
      season: "fall",
      daypart: "night",
      coolWeather: false,
      occasion: "dinner",
    });

    // No forecast: autumn counts as cool, and an all-day event is not evening.
    expect(
      contextFor(
        { date: "2026-10-01", weather: null, events: [event({ is_all_day: true, occasion: "travel" })] },
        "UTC",
      ),
    ).toEqual({ season: "fall", daypart: "day", coolWeather: true, occasion: "travel" });
  });
});
