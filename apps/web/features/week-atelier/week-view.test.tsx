import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fragranceDetail } from "@/test/catalog-fixtures";
import type { CalendarResult } from "@/lib/calendar";
import type { CalendarEvent } from "@/types/api";
import type { WearPlan, WearRecommendation } from "@/types/wear-intelligence";

import { buildWeek, eventSummary, noonOf, rangeLabel } from "./week-copy";
import { WeekView } from "./week-view";

const actions = vi.hoisted(() => ({ decide: vi.fn(), wear: vi.fn(), next: vi.fn(), feedback: vi.fn() }));
vi.mock("@/lib/server/recommendation-actions", () => ({ decideRecommendation: actions.decide, wearRecommendation: actions.wear, nextRecommendation: actions.next, recommendationFeedback: actions.feedback }));
const server = vi.hoisted(() => ({ updateCalendarEvent: vi.fn() }));
vi.mock("@/lib/server/actions", () => server);
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));
vi.mock("@/features/collection/wear-feedback-dialog", () => ({ WearFeedbackDialog: () => <p>How did it wear?</p> }));

function rec(date: string, id: string, name: string, overrides: Partial<WearRecommendation> = {}): WearRecommendation {
  return {
    id, context_key: `day:${date}`, recommended_for: `${date}T12:00:00Z`, generation_mode: "baseline", options_exhausted: false, remaining_options: 2, algorithm_version: "v",
    context: { context_key: `day:${date}`, recommended_for: `${date}T12:00:00Z`, local_date: date, timezone: "UTC", daypart: "day", season: "fall", occasion: "work", high_celsius: 5, condition: "rain", source: "day", weather_resolution: "daily", weather_stale: false } as WearRecommendation["context"],
    fragrance: fragranceDetail({ id: `f-${id}`, name }), score: 80, evidence_coverage: 0.7, recommended_sprays: 3, score_components: {}, reasons: ["A good fit"], warnings: [],
    alternatives: [{ fragrance: fragranceDetail({ id: "alt", name: "Alternative" }), score: 70, evidence_coverage: 0.5, recommended_sprays: 2, score_components: {}, reasons: ["Warmer for the evening"], warnings: [] }],
    decision: null,
    ...overrides,
  };
}

const plan: WearPlan = { local_date: "2026-11-14", timezone: "UTC", gaps: [], recommendations: [rec("2026-11-14", "r0", "Another 13"), rec("2026-11-15", "r1", "Silver Mountain Water")] };
const event: CalendarEvent = { id: "e1", title: "Team standup", starts_at: "2026-11-14T09:00:00Z", ends_at: "2026-11-14T09:30:00Z", is_all_day: false, location_label: null, occasion: "work", formality: null, is_hidden: false, calendar_name: null, provider: "google" };
const connected: CalendarResult = { status: "ok", events: [event], needsReconnect: false };

function renderWeek(calendar: CalendarResult = connected, extra: Partial<Parameters<typeof WeekView>[0]> = {}) {
  return render(<WeekView plan={plan} calendar={calendar} forecast={[{ date: "2026-11-14", condition: "cloudy", high_celsius: 7, low_celsius: 2, precipitation_probability: 0.1, humidity: null }]} location="Philadelphia" timeZone="UTC" unit="fahrenheit" {...extra} />);
}

beforeEach(() => {
  actions.decide.mockResolvedValue({ ok: true, data: {} });
  actions.wear.mockResolvedValue({ ok: true, data: { id: "w" } });
  actions.feedback.mockResolvedValue({ ok: true, data: {} });
  actions.next.mockResolvedValue({ ok: true, data: rec("2026-11-14", "r0", "By the Fireplace") });
  server.updateCalendarEvent.mockResolvedValue({ status: "success", message: "Event details saved." });
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: false, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(() => { vi.clearAllMocks(); vi.unstubAllGlobals(); });

describe("week helpers", () => {
  it("builds seven days with picks, events and forecast", () => {
    const days = buildWeek(plan, [event], [{ date: "2026-11-14", condition: "rain", high_celsius: 5, low_celsius: 1, precipitation_probability: 1, humidity: null }], "UTC", "fahrenheit");
    expect(days).toHaveLength(7);
    expect(days[0]).toMatchObject({ date: "2026-11-14", isToday: true, forecastLabel: "41° rain" });
    expect(days[0].events).toHaveLength(1);
    expect(days[1].recommendations[0].id).toBe("r1");
    expect(days[2].recommendations).toHaveLength(0);
    expect(rangeLabel("2026-11-14", "2026-11-20")).toBe("14 to 20 November");
    expect(rangeLabel("2026-11-28", "2026-12-04")).toBe("28 November to 4 December");
    expect(eventSummary([event, { ...event, id: "e2" }])).toBe("Team standup +1");
    expect(noonOf("2026-11-15", "UTC")).toBe("2026-11-15T12:00:00.000Z");
  });
});

describe("WeekView", () => {
  it("shows seven days, today selected, and empty days as Plan", () => {
    renderWeek();
    const cells = screen.getAllByTestId("day-cell");
    expect(cells).toHaveLength(7);
    expect(cells[0]).toHaveAttribute("aria-selected", "true");
    expect(within(cells[2]).getByText("Plan")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Another 13" })).toBeInTheDocument();
  });

  it("selects a day and shows its pick; an empty day says so", async () => {
    const user = userEvent.setup();
    renderWeek();
    await user.click(screen.getAllByTestId("day-cell")[1]);
    expect(await screen.findByRole("heading", { name: "Silver Mountain Water" })).toBeInTheDocument();
    await user.click(screen.getAllByTestId("day-cell")[3]);
    expect(await screen.findByRole("heading", { name: "Nothing planned for this day" })).toBeInTheDocument();
  });

  it("moves between days with the arrow keys", async () => {
    const user = userEvent.setup();
    renderWeek();
    screen.getAllByTestId("day-cell")[0].focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getAllByTestId("day-cell")[1]).toHaveAttribute("aria-selected", "true");
  });

  it("logs a wear on another day with that day's date", async () => {
    const user = userEvent.setup();
    renderWeek();
    await user.click(screen.getAllByTestId("day-cell")[1]);
    expect(await screen.findByRole("heading", { name: "Silver Mountain Water" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByRole("button", { name: "Wear it" })).toHaveLength(1));
    await user.click(screen.getByRole("button", { name: "Wear it" }));
    await user.click(await screen.findByRole("button", { name: "Log wear" }));
    await waitFor(() => expect(actions.wear).toHaveBeenCalledWith("r1", expect.objectContaining({ selected_fragrance_id: "f-r1", worn_at: "2026-11-15T12:00:00.000Z" })));
  });

  it("logs today's wear without a date and sends Not today", async () => {
    const user = userEvent.setup();
    renderWeek();
    await user.click(screen.getByRole("button", { name: "Not today" }));
    await waitFor(() => expect(actions.feedback).toHaveBeenCalledWith("r0", "f-r0", "not_today"));
    await waitFor(() => expect(actions.next).toHaveBeenCalled());
  });

  it("uses an alternative", async () => {
    const user = userEvent.setup();
    renderWeek();
    await user.click(screen.getByRole("button", { name: "Use this" }));
    await waitFor(() => expect(actions.decide).toHaveBeenCalledWith("r0", "replaced", "alt"));
    expect(await screen.findByRole("button", { name: "Planned" })).toBeDisabled();
  });

  it("edits an event with the existing correction form", async () => {
    const user = userEvent.setup();
    renderWeek();
    await user.click(screen.getByRole("button", { name: "Edit Team standup" }));
    const sheet = await screen.findByRole("dialog", { name: "Edit Team standup" });
    await user.selectOptions(within(sheet).getByLabelText("Occasion"), "dinner");
    await user.click(within(sheet).getByRole("button", { name: "Save event details" }));
    await waitFor(() => expect(server.updateCalendarEvent).toHaveBeenCalled());
    const form = server.updateCalendarEvent.mock.calls[0][1] as FormData;
    expect(Object.fromEntries(form)).toEqual({ event_id: "e1", occasion: "dinner", formality: "", setting: "" });
  });

  it("offers to connect a calendar when none is connected", () => {
    renderWeek({ status: "not_connected" });
    expect(screen.queryByRole("heading", { name: "Your day" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Connect a calendar" })).toHaveAttribute("href", "/settings#calendar");
  });

  it("asks to reconnect", () => {
    renderWeek({ status: "ok", events: [], needsReconnect: true });
    expect(screen.getByRole("link", { name: "Reconnect" })).toBeInTheDocument();
  });

  it("shows the empty collection state", () => {
    renderWeek(connected, { emptyCollection: true });
    expect(screen.getByRole("heading", { name: "Your shelf starts here" })).toBeInTheDocument();
  });
});
