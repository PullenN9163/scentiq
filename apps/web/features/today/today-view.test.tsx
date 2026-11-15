import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { collectionInsights, fragranceDetail } from "@/test/catalog-fixtures";
import type { CalendarResult } from "@/lib/calendar";
import type { WeatherResult } from "@/lib/weather";
import type { Me } from "@/types/api";
import type { WearPlan, WearRecommendation } from "@/types/wear-intelligence";

import { TodayView } from "./today-view";

const actions = vi.hoisted(() => ({
  decide: vi.fn(),
  wear: vi.fn(),
  next: vi.fn(),
  feedback: vi.fn(),
}));
vi.mock("@/lib/server/recommendation-actions", () => ({
  decideRecommendation: actions.decide,
  wearRecommendation: actions.wear,
  nextRecommendation: actions.next,
  recommendationFeedback: actions.feedback,
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));
vi.mock("@/features/collection/wear-feedback-dialog", () => ({ WearFeedbackDialog: () => <p>How did it wear?</p> }));

const me: Me = {
  id: "m1", email: "m@example.test", display_name: "Maya", lifecycle_state: "active", created_at: "2026-01-01T00:00:00Z",
  preferences: { location: "Philadelphia", location_label: "Philadelphia, PA", timezone: "America/New_York", temperature_unit: "fahrenheit", preferred_season: null, preferred_occasion: null, preferred_projection: null, preferred_longevity: null, maximum_sprays: null },
};

function recommendation(overrides: Partial<WearRecommendation> = {}): WearRecommendation {
  const fragrance = fragranceDetail({ id: "f1", name: "Another 13", top_accords: ["Musky", "Woody"], brand: { id: "b", name: "Le Labo", slug: "le-labo", country: null } });
  return {
    id: "rec1", context_key: "day:2026-11-14", recommended_for: "2026-11-14T12:00:00Z", generation_mode: "baseline", options_exhausted: false, remaining_options: 2, algorithm_version: "wear-v2",
    context: { context_key: "day:2026-11-14", recommended_for: "2026-11-14T12:00:00Z", local_date: "2026-11-14", timezone: "America/New_York", daypart: "day", season: "fall", occasion: "work", source: "day", weather_resolution: "unavailable", weather_stale: false } as WearRecommendation["context"],
    fragrance, score: 80.4, evidence_coverage: 0.7, recommended_sprays: 3, score_components: { occasion: 12.5 },
    reasons: ["Clean musk that stays close for a cool day", "Not worn in 12 days"], warnings: [], alternatives: [], decision: null,
    ...overrides,
  };
}

const nextPick = recommendation({ id: "rec1", fragrance: fragranceDetail({ id: "f2", name: "By the Fireplace" }), reasons: ["A warmer choice"] });
const okWeather: WeatherResult = { status: "ok", forecast: { location_label: "Philadelphia, PA", timezone: "America/New_York", temperature_unit: "fahrenheit", fetched_at: "", stale: false, days: [{ date: "2026-11-14", condition: "cloudy", high_celsius: 7.2, low_celsius: 2, precipitation_probability: 0.1, humidity: null }] } };
const connected: CalendarResult = { status: "ok", events: [], needsReconnect: false };

function renderToday({ plan = { local_date: "2026-11-14", timezone: "America/New_York", gaps: [], recommendations: [recommendation()] } as WearPlan, weather = okWeather, calendar = connected, totalItems = 12, planFailed = false }: { planFailed?: boolean; plan?: WearPlan; weather?: WeatherResult; calendar?: CalendarResult; totalItems?: number } = {}) {
  return render(
    <TodayView plan={plan} planFailed={planFailed} me={me} insights={collectionInsights({ total_items: totalItems })} recentWears={[]} weather={weather} calendar={calendar} timeZone="America/New_York" />,
  );
}

beforeEach(() => {
  actions.decide.mockResolvedValue({ ok: true, data: {} });
  actions.wear.mockResolvedValue({ ok: true, data: { id: "wear1" } });
  actions.next.mockResolvedValue({ ok: true, data: nextPick });
  actions.feedback.mockResolvedValue({ ok: true, data: {} });
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: false, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
});
afterEach(() => { vi.clearAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers(); });

describe("TodayView responses", () => {
  it("keeps the page and offers a retry when the pick could not be loaded", () => {
    renderToday({ plan: { local_date: "2026-11-14", timezone: "America/New_York", gaps: [], recommendations: [] } as WearPlan, planFailed: true });
    expect(screen.getByRole("heading", { name: /could not load today.s pick/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
    expect(screen.queryByText(/Add an owned fragrance/)).not.toBeInTheDocument();
  });

  it("shows the pick with its chips, reason and score", () => {
    renderToday();
    const hero = screen.getByTestId("recommendation-hero");
    expect(within(hero).getByRole("heading", { name: "Another 13" })).toBeInTheDocument();
    expect(within(hero).getByText("45°F cloudy")).toBeInTheDocument();
    expect(within(hero).getByText("Work")).toBeInTheDocument();
    expect(within(hero).getByText("Not worn in 12 days")).toBeInTheDocument();
    expect(within(hero).getByText("Clean musk that stays close for a cool day.")).toBeInTheDocument();
    expect(within(hero).getByRole("button", { name: /Match 80/ })).toBeInTheDocument();
    for (const old of ["Accept", "Dismiss", "View alternatives", "Another Option", "Why this?", "Layer It"]) {
      expect(screen.queryByRole("button", { name: old })).not.toBeInTheDocument();
    }
  });

  it("logs a wear from the wear sheet", async () => {
    const user = userEvent.setup();
    renderToday();
    await user.click(screen.getByRole("button", { name: "Wear it" }));
    const sheet = await screen.findByRole("dialog", { name: "Wear Another 13" });
    await user.click(within(sheet).getByRole("button", { name: "More sprays" }));
    await user.click(screen.getByRole("button", { name: "Log wear" }));
    await waitFor(() => expect(actions.wear).toHaveBeenCalledWith("rec1", { selected_fragrance_id: "f1", sprays: 4, notes: null, occasion: "work", setting: null }));
    expect(await screen.findByText("How did it wear?")).toBeInTheDocument();
  });

  it("sends not_today and then asks for the next pick", async () => {
    const user = userEvent.setup();
    renderToday();
    await user.click(screen.getByRole("button", { name: "Not today" }));
    await waitFor(() => expect(actions.next).toHaveBeenCalled());
    expect(actions.feedback).toHaveBeenCalledWith("rec1", "f1", "not_today");
    expect(actions.next).toHaveBeenCalledWith("rec1", expect.any(String), false, "f1");
    expect(await screen.findByRole("heading", { name: "By the Fireplace" })).toBeInTheDocument();
  });

  it("asks Too strong? and sends too_strong on Yes", async () => {
    const user = userEvent.setup();
    renderToday();
    await user.click(screen.getByRole("button", { name: "Not for me" }));
    const group = screen.getByRole("group", { name: "Too strong?" });
    await user.click(within(group).getByRole("button", { name: "Yes" }));
    await waitFor(() => expect(actions.feedback).toHaveBeenCalledWith("rec1", "f1", "too_strong"));
    await waitFor(() => expect(actions.next).toHaveBeenCalled());
  });

  it("sends dislike_scent on Skip", async () => {
    const user = userEvent.setup();
    renderToday();
    await user.click(screen.getByRole("button", { name: "Not for me" }));
    await user.click(screen.getByRole("button", { name: "Skip" }));
    await waitFor(() => expect(actions.feedback).toHaveBeenCalledWith("rec1", "f1", "dislike_scent"));
  });

  it("sends dislike_scent when Too strong? goes unanswered", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderToday();
    await user.click(screen.getByRole("button", { name: "Not for me" }));
    await act(async () => { vi.advanceTimersByTime(10_500); });
    await waitFor(() => expect(actions.feedback).toHaveBeenCalledWith("rec1", "f1", "dislike_scent"));
  });

  it("keeps the last pick when options are exhausted and can start over", async () => {
    const user = userEvent.setup();
    renderToday({ plan: { local_date: "2026-11-14", timezone: "UTC", gaps: [], recommendations: [recommendation({ options_exhausted: true })] } });
    expect(screen.getByText("That is everything for today.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Not today" }));
    await waitFor(() => expect(actions.feedback).toHaveBeenCalledWith("rec1", "f1", "not_today"));
    expect(actions.next).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Start over" }));
    await waitFor(() => expect(actions.next).toHaveBeenCalledWith("rec1", expect.any(String), true, "f1"));
  });

  it("reuses the idempotency key when retrying a failed advance", async () => {
    const user = userEvent.setup();
    actions.next.mockResolvedValueOnce({ ok: false, error: "Could not get another option. Try again." });
    renderToday();
    await user.click(screen.getByRole("button", { name: "Not today" }));
    expect(await screen.findByText("Could not get another option. Try again.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Not today" }));
    await waitFor(() => expect(actions.next).toHaveBeenCalledTimes(2));
    expect(actions.next.mock.calls[0][1]).toBe(actions.next.mock.calls[1][1]);
  });

  it("shows action errors inline", async () => {
    const user = userEvent.setup();
    actions.feedback.mockResolvedValueOnce({ ok: false, error: "Could not save feedback. Try again." });
    renderToday();
    await user.click(screen.getByRole("button", { name: "Not today" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not save feedback. Try again.");
  });
});

describe("TodayView states", () => {
  it("shows the empty shelf state", () => {
    renderToday({ totalItems: 0 });
    expect(screen.getByRole("heading", { name: "Your shelf starts here" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Add fragrance" })).toHaveAttribute("href", "/collection");
    expect(screen.queryByTestId("recommendation-hero")).not.toBeInTheDocument();
  });

  it.each(["location_required", "location_unresolved"] as const)("offers to add a location for %s", (status) => {
    renderToday({ weather: { status } });
    expect(screen.getByRole("link", { name: "Add your location" })).toHaveAttribute("href", "/settings");
  });

  it("leaves out the weather chip when the forecast is unavailable", () => {
    renderToday({ weather: { status: "unavailable" } });
    expect(screen.queryByText(/°F/)).not.toBeInTheDocument();
    expect(screen.queryByText("Add your location")).not.toBeInTheDocument();
  });

  it("drops the occasion chip and offers a calendar when none is connected", async () => {
    const user = userEvent.setup();
    renderToday({ calendar: { status: "not_connected" } });
    expect(within(screen.getByTestId("recommendation-hero")).queryByText("Work")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Connect a calendar" })).toHaveAttribute("href", "/settings#calendar");
    await user.click(screen.getByRole("button", { name: "Dismiss calendar suggestion" }));
    expect(screen.queryByRole("link", { name: "Connect a calendar" })).not.toBeInTheDocument();
  });

  it("asks to reconnect a calendar that needs it", () => {
    renderToday({ calendar: { status: "ok", events: [], needsReconnect: true } });
    expect(screen.getByRole("link", { name: "Reconnect" })).toHaveAttribute("href", "/settings#calendar");
  });

  it("restyles the no-recommendation message as an empty state", () => {
    renderToday({ plan: { local_date: "2026-11-14", timezone: "UTC", gaps: [], recommendations: [] } });
    expect(screen.getByRole("heading", { name: "Add an owned fragrance to receive recommendations." })).toBeInTheDocument();
  });

  it("shows plan gaps as one quiet line", () => {
    renderToday({ plan: { local_date: "2026-11-14", timezone: "UTC", gaps: ["No evening pick: nothing suits a formal dinner."], recommendations: [recommendation()] } });
    expect(screen.getByText("No evening pick: nothing suits a formal dinner.")).toBeInTheDocument();
  });

  it("shows Later today only with more than one recommendation, and plans it", async () => {
    const user = userEvent.setup();
    const { unmount } = renderToday();
    expect(screen.queryByRole("heading", { name: "Later today" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Start a blend with Another 13/ })).toHaveAttribute("href", "/layering?a=f1");
    unmount();
    const evening = recommendation({ id: "rec2", fragrance: fragranceDetail({ id: "f3", name: "Tobacco Vanille" }), context: { ...recommendation().context, daypart: "night", occasion: "dinner" } });
    renderToday({ plan: { local_date: "2026-11-14", timezone: "UTC", gaps: [], recommendations: [recommendation(), evening] } });
    expect(screen.getByRole("heading", { name: "Later today" })).toBeInTheDocument();
    expect(screen.getByText("Tonight · Dinner")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Blend Another 13 with Tobacco Vanille/ })).toHaveAttribute("href", "/layering?a=f1");
    await user.click(screen.getByRole("button", { name: "Plan it" }));
    await waitFor(() => expect(actions.decide).toHaveBeenCalledWith("rec2", "accepted", "f3"));
    expect(await screen.findByRole("button", { name: "Planned" })).toBeDisabled();
  });
});
