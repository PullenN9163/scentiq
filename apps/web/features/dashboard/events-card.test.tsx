import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { EventsCard } from "./events-card";
import type { CalendarEvent } from "@/types/api";
import { updateCalendarEvent } from "@/lib/server/actions";

vi.mock("@/lib/server/actions", () => ({
  updateCalendarEvent: vi.fn().mockResolvedValue({ status: "success", message: "Event details saved." }),
}));

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
  it("lets members correct an event occasion and setting", async () => {
    const user = userEvent.setup();
    render(<EventsCard calendar={{ status: "ok", events: [standup], needsReconnect: false }} timeZone="UTC" />);
    await user.click(screen.getByText("Correct event details"));
    await user.selectOptions(screen.getByLabelText("Occasion"), "formal");
    await user.selectOptions(screen.getByLabelText("Setting"), "outdoor");
    await user.click(screen.getByRole("button", { name: "Save event details" }));
    await waitFor(() => expect(updateCalendarEvent).toHaveBeenCalled());
    const data = vi.mocked(updateCalendarEvent).mock.calls.at(-1)?.[1];
    expect(data?.get("event_id")).toBe("e1");
    expect(data?.get("occasion")).toBe("formal");
    expect(data?.get("setting")).toBe("outdoor");
  });
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
