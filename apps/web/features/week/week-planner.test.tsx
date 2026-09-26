import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import type { PlanDay } from "@/lib/week";
import { fragranceDetail } from "@/test/catalog-fixtures";

import { WeekPlanner } from "./week-planner";

afterEach(cleanup);

const owned = [
  fragranceDetail(),
  fragranceDetail({
    id: "22222222-2222-4222-8222-222222222222",
    name: "Second Source Scent",
    rating_average: 3.8,
  }),
];

const days: PlanDay[] = [
  "2026-09-26",
  "2026-09-27",
  "2026-09-28",
  "2026-09-29",
  "2026-09-30",
  "2026-10-01",
  "2026-10-02",
].map((date) => ({ date, weather: null, events: [] }));
days[0] = {
  date: "2026-09-26",
  weather: {
    date: "2026-09-26",
    condition: "rain",
    high_celsius: 15,
    low_celsius: 8,
    precipitation_probability: 0.7,
    humidity: 80,
  },
  events: [
    {
      id: "e1",
      title: "Anniversary dinner",
      starts_at: "2026-09-26T19:30:00Z",
      ends_at: "2026-09-26T21:30:00Z",
      is_all_day: false,
      location_label: null,
      occasion: "date",
      formality: "smart",
      is_hidden: false,
      calendar_name: "Personal",
      provider: "google",
    },
  ],
};

function renderPlanner(overrides: Partial<Parameters<typeof WeekPlanner>[0]> = {}) {
  return render(
    <WeekPlanner
      owned={owned}
      days={days}
      timeZone="UTC"
      temperatureUnit="fahrenheit"
      weatherStatus="ok"
      calendarStatus="ok"
      {...overrides}
    />,
  );
}

describe("WeekPlanner", () => {
  it("renders all seven days and cycles through owned fragrances", async () => {
    const user = userEvent.setup();
    renderPlanner();

    expect(screen.getAllByTestId("week-day")).toHaveLength(7);
    await user.click(screen.getAllByRole("button", { name: /alternative/i })[0]);
    expect(screen.getAllByText("Second Source Scent").length).toBeGreaterThan(0);
  });

  it("shows each day's real forecast and events", () => {
    renderPlanner();

    expect(screen.getByText("Sep 26 – Oct 2")).toBeInTheDocument();
    expect(screen.getByText(/59°F/)).toBeInTheDocument();
    expect(screen.getByText("Anniversary dinner")).toBeInTheDocument();
    expect(screen.getByText("19:30")).toBeInTheDocument();
    expect(screen.getAllByText("Open day")).toHaveLength(6);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("explains missing inputs without inventing them", () => {
    renderPlanner({ weatherStatus: "location_required", calendarStatus: "not_connected" });

    const notes = screen.getByRole("status");
    expect(notes).toHaveTextContent(/Add your location/);
    expect(notes).toHaveTextContent(/Connect a calendar/);
  });

  it("does not fabricate a recommendation for an empty collection", () => {
    renderPlanner({ owned: [] });
    expect(screen.getByText("Your collection is empty")).toBeVisible();
  });
});
