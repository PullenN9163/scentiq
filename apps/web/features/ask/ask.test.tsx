import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fragranceSummary } from "@/test/catalog-fixtures";

import { AskProvider, useAsk } from "./ask-provider";
import { AskResult } from "./ask-results";
import { contextPrefix } from "./use-ask-thread";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }), usePathname: () => "/dashboard" }));
const wear = vi.hoisted(() => vi.fn());
vi.mock("@/lib/server/recommendation-actions", () => ({ wearRecommendation: wear }));

function ndjson(events: unknown[], { hold = false }: { hold?: boolean } = {}) {
  const encoder = new TextEncoder();
  let release: () => void = () => {};
  const gate = new Promise<void>((resolve) => { release = resolve; });
  const body = new ReadableStream<Uint8Array>({
    async start(controller) {
      for (const [index, event] of events.entries()) {
        if (hold && index === events.length - 1) await gate;
        controller.enqueue(encoder.encode(`${JSON.stringify(event)}\n`));
      }
      controller.close();
    },
  });
  return { response: new Response(body, { status: 200 }), release };
}

const fetchMock = vi.fn();
beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: false, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  Element.prototype.scrollIntoView = vi.fn();
  wear.mockResolvedValue({ ok: true, data: { id: "w1" } });
});
afterEach(() => { vi.clearAllMocks(); vi.unstubAllGlobals(); });

function Opener({ about }: { about?: boolean }) {
  const ask = useAsk();
  return <button onClick={() => ask(about ? { fragranceId: "f1", name: "Another 13", brand: "Le Labo" } : null)}>Open Ask</button>;
}

function renderAsk(about = false) {
  render(<AskProvider><Opener about={about} /></AskProvider>);
}

describe("Ask panel", () => {
  it("shows the empty state with quick prompts", async () => {
    const user = userEvent.setup();
    renderAsk();
    await user.click(screen.getByRole("button", { name: "Open Ask" }));
    const panel = await screen.findByRole("dialog", { name: "Ask" });
    expect(within(panel).getByRole("heading", { name: "What should we decide?" })).toBeInTheDocument();
    for (const label of ["Wear today", "Plan my week", "What am I neglecting?", "Layer this", "What should I buy next?"]) {
      expect(within(panel).getByRole("button", { name: label })).toBeInTheDocument();
    }
    expect(within(panel).getByText("Your conversation stays in this session.")).toBeInTheDocument();
  });

  it("streams status, text and cards and clears the status at done", async () => {
    const user = userEvent.setup();
    const stream = ndjson([
      { type: "status", label: "Checking your week…" },
      { type: "text_delta", delta: "Wear " },
      { type: "text_delta", delta: "Another 13." },
      { type: "card", card: { kind: "fragrance", data: fragranceSummary({ id: "f9", name: "Santal 33" }) } },
      { type: "done" },
    ], { hold: true });
    fetchMock.mockResolvedValue(stream.response);
    renderAsk();
    await user.click(screen.getByRole("button", { name: "Open Ask" }));
    await user.type(await screen.findByLabelText("Ask about your collection"), "What today?{Enter}");
    expect(await screen.findByText("Checking your week…")).toBeInTheDocument();
    expect(await screen.findByText("Wear Another 13.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Stop" })).toBeInTheDocument();
    stream.release();
    await waitFor(() => expect(screen.queryByText("Checking your week…")).not.toBeInTheDocument());
    expect(screen.getByRole("link", { name: /Santal 33/ })).toHaveAttribute("href", "/collection/f9");
    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ message: "What today?", history: [] });
  });

  it("prefixes the first message with the fragrance it was opened from", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(ndjson([{ type: "done" }]).response);
    renderAsk(true);
    await user.click(screen.getByRole("button", { name: "Open Ask" }));
    expect(await screen.findByText("About Another 13")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Ask about your collection"), "Is it good for work?{Enter}");
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).message).toBe("About Another 13 by Le Labo: Is it good for work?");
    expect(screen.getByText("Is it good for work?")).toBeInTheDocument();
    expect(screen.queryByText("About Another 13")).not.toBeInTheDocument();
    expect(contextPrefix({ fragranceId: "f", name: "A", brand: "B" })).toBe("About A by B: ");
  });

  it("keeps Shift+Enter as a new line and closes on Escape", async () => {
    const user = userEvent.setup();
    renderAsk();
    await user.click(screen.getByRole("button", { name: "Open Ask" }));
    const field = await screen.findByLabelText("Ask about your collection");
    await user.type(field, "Line one{Shift>}{Enter}{/Shift}Line two");
    expect(fetchMock).not.toHaveBeenCalled();
    expect(field).toHaveValue("Line one\nLine two");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("shows an interrupted stream as an error with Try again", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(ndjson([{ type: "text_delta", delta: "Partial" }]).response);
    fetchMock.mockResolvedValueOnce(ndjson([{ type: "done" }]).response);
    renderAsk();
    await user.click(screen.getByRole("button", { name: "Open Ask" }));
    await user.type(await screen.findByLabelText("Ask about your collection"), "Hello{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("Advisor response was interrupted. Please try again.");
    await user.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });

  it("opens with Ctrl K", async () => {
    const user = userEvent.setup();
    renderAsk();
    await user.keyboard("{Control>}k{/Control}");
    expect(await screen.findByRole("dialog", { name: "Ask" })).toBeInTheDocument();
  });
});

describe("Ask result cards", () => {
  const recommendation = { id: "r1", fragrance: fragranceSummary({ id: "f1", name: "Another 13" }), alternatives: [], context: { local_date: "2026-11-16", occasion: "work", daypart: "day" }, recommended_sprays: 3 };

  it("renders recommendations as rows with Wear it", async () => {
    const user = userEvent.setup();
    render(<AskResult card={{ kind: "recommendation", data: recommendation }} />);
    expect(screen.getByRole("link", { name: /Another 13/ })).toHaveAttribute("href", "/collection/f1");
    await user.click(screen.getByRole("button", { name: "Wear it" }));
    await waitFor(() => expect(wear).toHaveBeenCalledWith("r1", { selected_fragrance_id: "f1", sprays: 3, occasion: "work", setting: null, notes: null }));
    expect(screen.getByRole("link", { name: "Open Today" })).toHaveAttribute("href", "/dashboard");
  });

  it("renders a week", () => {
    render(<AskResult card={{ kind: "week", data: { recommendations: [recommendation], gaps: [] } }} />);
    expect(screen.getByText("Mon · Work")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Week" })).toHaveAttribute("href", "/week");
  });

  it("renders layering stacks as a vial with Open in Blend", () => {
    const stack = { mode: "balanced", goal: "warmer", score: 0.78, verdict: "Strong fit", items: [{ fragrance: fragranceSummary({ id: "a", name: "Alpha" }), application_order: 1, suggested_sprays: 2, role: "anchor" }, { fragrance: fragranceSummary({ id: "b", name: "Beta" }), application_order: 2, suggested_sprays: 1, role: "accent" }] };
    render(<AskResult card={{ kind: "layering", data: [stack] }} />);
    expect(screen.getByText("Alpha + Beta")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open in Blend" })).toHaveAttribute("href", "/layering?stack=a%2Cb&mode=balanced&goal=warmer");
  });

  it("renders insights, wears, collection and discover", () => {
    const { unmount } = render(<AskResult card={{ kind: "insights", data: { owned_items: 22, total_wears: 42, most_worn: [{ fragrance_id: "f1", fragrance_name: "Another 13", wear_count: 9 }] } }} />);
    expect(screen.getByText("22 owned · 42 wears recorded")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Your taste" })).toHaveAttribute("href", "/insights");
    unmount();
    const second = render(<AskResult card={{ kind: "wears", data: [{ fragrance_name: "Another 13", worn_at: "2026-11-10T10:00:00Z" }] }} />);
    expect(screen.getByText("2026-11-10")).toBeInTheDocument();
    second.unmount();
    const third = render(<AskResult card={{ kind: "discover", data: [{ fragrance: fragranceSummary({ id: "d1", name: "Discovery" }), reasons: ["Adds something new"] }] }} />);
    expect(screen.getByText("Adds something new")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Discover" })).toBeInTheDocument();
    third.unmount();
    render(<AskResult card={{ kind: "collection", data: [] }} />);
    expect(screen.getByText("No matching results in your recorded data.")).toBeInTheDocument();
  });
});
