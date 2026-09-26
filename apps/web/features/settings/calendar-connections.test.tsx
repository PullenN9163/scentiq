import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CalendarConnectionsCard } from "./calendar-connections";
import type { CalendarConnection, CalendarProviderStatus } from "@/types/api";

vi.mock("@/lib/server/actions", () => ({
  disconnectCalendar: vi.fn(),
  setCalendarSelected: vi.fn(),
  syncCalendarConnection: vi.fn(),
}));

const providers: CalendarProviderStatus[] = [
  { provider: "google", available: true },
  { provider: "microsoft", available: false },
];

function connection(overrides: Partial<CalendarConnection> = {}): CalendarConnection {
  return {
    id: "c1",
    provider: "google",
    account_email: "member@example.com",
    status: "active",
    last_synced_at: "2026-09-26T12:00:00Z",
    last_error_code: null,
    sources: [
      { id: "s1", name: "Personal", color: null, is_primary: true, is_selected: true },
      { id: "s2", name: "Holidays", color: null, is_primary: false, is_selected: false },
    ],
    ...overrides,
  };
}

describe("CalendarConnectionsCard", () => {
  it("offers to connect available providers only", () => {
    render(<CalendarConnectionsCard providers={providers} connections={[]} notice={null} />);

    expect(screen.getByRole("link", { name: /Connect Google Calendar/ })).toHaveAttribute(
      "href",
      "/integrations/calendar/google/start",
    );
    expect(screen.getByRole("button", { name: /Outlook Calendar/ })).toBeDisabled();
  });

  it("lists a connection with its calendars", () => {
    render(
      <CalendarConnectionsCard providers={providers} connections={[connection()]} notice={null} />,
    );

    const panel = screen.getByRole("region", { name: "member@example.com" });
    expect(within(panel).getByText("Connected")).toBeInTheDocument();
    expect(within(panel).getByRole("checkbox", { name: "Include Personal" })).toBeChecked();
    expect(within(panel).getByRole("checkbox", { name: "Include Holidays" })).not.toBeChecked();
    expect(within(panel).getByRole("button", { name: /Sync now/ })).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Connect another Google Calendar account/ }),
    ).toBeInTheDocument();
  });

  it("asks to reconnect a lapsed grant", () => {
    render(
      <CalendarConnectionsCard
        providers={providers}
        connections={[connection({ status: "reauth_required", last_error_code: "reauth_required" })]}
        notice={null}
      />,
    );

    expect(screen.getByText("Reconnect needed")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Reconnect" })).toHaveAttribute(
      "href",
      "/integrations/calendar/google/start",
    );
    expect(screen.queryByRole("button", { name: /Sync now/ })).not.toBeInTheDocument();
  });

  it("notes a failed sync while still active", () => {
    render(
      <CalendarConnectionsCard
        providers={providers}
        connections={[connection({ last_error_code: "provider_unavailable" })]}
        notice={null}
      />,
    );
    expect(screen.getByText(/last sync failed/)).toBeInTheDocument();
  });

  it("shows the outcome of the OAuth round trip", () => {
    const { rerender } = render(
      <CalendarConnectionsCard providers={providers} connections={[]} notice="connected" />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(/Calendar connected/);

    rerender(
      <CalendarConnectionsCard providers={providers} connections={[]} notice="access_denied" />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/not granted/);

    rerender(<CalendarConnectionsCard providers={providers} connections={[]} notice="bogus" />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("degrades when calendar data could not be loaded", () => {
    render(<CalendarConnectionsCard providers={null} connections={null} notice={null} />);
    expect(screen.getByRole("status")).toHaveTextContent(/can't be loaded/);
  });
});
