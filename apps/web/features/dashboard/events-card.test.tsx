import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EventsCard } from "./events-card";
import type { CalendarEvent } from "@/types/api";

const standup: CalendarEvent = {
  id: "e1",
  title: "Standup",
  starts_at: "2026-09-26T13:30:00Z",
  ends_at: "2026-09-26T13:45:00Z",
  is_all_day: false,
  location_label: null,
  occasion: "work",
  formality: "smart",
  is_hidden: false,
  calendar_name: "Personal",
  provider: "google",
};

describe("EventsCard", () => {
  it("lists today's events in the member's timezone", () => {
    render(
      <EventsCard
        calendar={{ status: "ok", events: [standup], needsReconnect: false }}
        timeZone="America/New_York"
      />,
    );

    expect(screen.getByText("09:30")).toBeInTheDocument();
    expect(screen.getByText("Standup")).toBeInTheDocument();
    expect(screen.getByText("Work")).toBeInTheDocument();
  });

  it("calls out an open day", () => {
    render(<EventsCard calendar={{ status: "ok", events: [], needsReconnect: false }} timeZone="UTC" />);
    expect(screen.getByText(/open day/)).toBeInTheDocument();
  });

  it("nudges toward reconnecting", () => {
    render(<EventsCard calendar={{ status: "ok", events: [], needsReconnect: true }} timeZone="UTC" />);
    expect(screen.getByRole("status")).toHaveTextContent(/needs reconnecting/);
  });

  it("invites a first connection", () => {
    render(<EventsCard calendar={{ status: "not_connected" }} timeZone="UTC" />);
    expect(screen.getByRole("link", { name: "Connect a calendar" })).toHaveAttribute(
      "href",
      "/settings#calendar",
    );
  });

  it("degrades when the calendar is unavailable", () => {
    render(<EventsCard calendar={{ status: "unavailable" }} timeZone="UTC" />);
    expect(screen.getByRole("status")).toHaveTextContent(/can't be loaded/);
  });
});
