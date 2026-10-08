import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AgentExperience } from "./agent-experience";

vi.mock("@/features/recommendations/recommendation-card", () => ({ RecommendationCard: () => null }));

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function response(events: unknown[]) {
  return new Response(events.map((event) => JSON.stringify(event)).join("\n") + "\n", { headers: { "Content-Type": "application/x-ndjson" } });
}

describe("AgentExperience", () => {
  it("sends free text with bounded session history and renders grounded cards", async () => {
    const fetcher = vi.fn().mockResolvedValue(response([
      { type: "tool_started", tool: "get_collection_insights", label: "Comparing your collection…" },
      { type: "fallback", label: "AI explanation unavailable — showing ScentIQ's structured answer" },
      { type: "card", card: { kind: "insights", data: { total_wears: 3, total_purchase_value: "120.00", owned_items: 2 } } },
      { type: "text_delta", delta: "You have recorded three wears." }, { type: "done" },
    ]));
    vi.stubGlobal("fetch", fetcher);
    const user = userEvent.setup();
    render(<AgentExperience authenticated />);
    await user.type(screen.getByRole("textbox", { name: "Ask your fragrance advisor" }), "What is my most worn fragrance?");
    await user.keyboard("{Enter}");
    await waitFor(() => expect(screen.getByText("You have recorded three wears.")).toBeVisible());
    expect(fetcher.mock.calls[0][0]).toBe("/api/agent/chat");
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({ message: "What is my most worn fragrance?", history: [] });
    expect(screen.getByText(/AI explanation unavailable/)).toBeVisible();
    expect(screen.getByRole("link", { name: "Open Insights" })).toHaveAttribute("href", "/insights");
    expect(screen.queryByText("get_collection_insights")).not.toBeInTheDocument();
  });

  it("keeps Shift+Enter as a newline and disables an unauthenticated composer", async () => {
    const user = userEvent.setup();
    const view = render(<AgentExperience authenticated />);
    const input = screen.getByRole("textbox", { name: "Ask your fragrance advisor" });
    await user.type(input, "Dinner");
    await user.keyboard("{Shift>}{Enter}{/Shift}");
    expect(input).toHaveValue("Dinner\n");
    view.rerender(<AgentExperience authenticated={false} />);
    expect(input).toBeDisabled();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("aborts the active stream and exposes a useful interrupted state", async () => {
    let signal: AbortSignal | undefined;
    vi.stubGlobal("fetch", vi.fn((_url: string, init: RequestInit) => {
      signal = init.signal as AbortSignal;
      return new Promise((_resolve, reject) => signal?.addEventListener("abort", () => reject(new DOMException("Stopped", "AbortError"))));
    }));
    const user = userEvent.setup();
    render(<AgentExperience authenticated />);
    await user.click(screen.getByRole("button", { name: "Wear today" }));
    await user.click(screen.getByRole("button", { name: "Stop" }));
    await waitFor(() => expect(signal?.aborted).toBe(true));
    expect(await screen.findByRole("alert")).toHaveTextContent("Response stopped.");
  });
});
