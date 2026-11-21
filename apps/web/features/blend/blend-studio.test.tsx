import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { fragranceSummary } from "@/test/catalog-fixtures";
import type { CollectionItem } from "@/types/api";
import type { LayeringStackSuggestion } from "@/types/layering";

import { BlendStudio } from "./blend-studio";
import { initialBlend } from "./blend-state";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }));
const layering = vi.hoisted(() => ({ evaluateLayerStack: vi.fn(), getLayeringIntelligence: vi.fn(), saveLayerStack: vi.fn(), logLayerStackWear: vi.fn(), rateLayerStackWear: vi.fn() }));
vi.mock("@/lib/server/layering-actions", () => layering);

const names = ["Cedar Drift", "Amber Hour", "Silver Mist"];
const owned: CollectionItem[] = names.map((name, index) => ({
  id: `item-${index}`, fragrance: fragranceSummary({ id: `00000000-0000-4000-8000-00000000000${index + 1}`, name, top_accords: ["Woody"] }),
  ownership_type: "bottle", status: "owned", bottle_size_ml: 100, remaining_ml: 50, user_rating: null, purchase_price: null, purchase_date: null, custom_longevity: null, custom_projection: null,
}));

function reading(ids: string[]): LayeringStackSuggestion {
  const items = ids.map((id, index) => ({ fragrance: owned.find((item) => item.fragrance.id === id)!.fragrance, role: index ? "accent" : "anchor", application_order: index + 1, suggested_sprays: index ? 1 : 2 }));
  return { items, mode: "balanced", goal: null, score: 0.78, verdict: "Strong fit", shared_notes: ["Cedar"], bridge_signals: [], explanation: { why_they_fit: [], what_changes: [], watch_out_for: [] }, warnings: [], evidence_summary: "Some information missing" } as unknown as LayeringStackSuggestion;
}

beforeEach(() => {
  // jsdom has no canvas; mist is skipped without one.
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: false, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  layering.evaluateLayerStack.mockImplementation(async (ids: string[]) => reading(ids));
});

describe("BlendStudio", () => {
  it("adds and removes bottles from the keyboard and reads the blend", async () => {
    const user = userEvent.setup();
    render(<BlendStudio owned={owned} saved={[]} start={initialBlend()} />);
    const shelf = screen.getByRole("list", { name: "Your shelf" });
    const cedar = within(shelf).getByRole("button", { name: "Add Cedar Drift" });
    cedar.focus();
    await user.keyboard("{Enter}");
    expect(within(shelf).getByRole("button", { name: "Remove Cedar Drift" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Add a second bottle")).toBeInTheDocument();

    await user.keyboard("{ArrowRight}");
    expect(within(shelf).getByRole("button", { name: "Add Amber Hour" })).toHaveFocus();
    await user.keyboard(" ");
    await waitFor(() => expect(screen.getByText("Strong fit")).toBeInTheDocument(), { timeout: 2000 });
    expect(layering.evaluateLayerStack).toHaveBeenLastCalledWith([owned[0].fragrance.id, owned[1].fragrance.id], "balanced", null);
    expect(screen.getByText("78")).toBeInTheDocument();
    expect(screen.getByText("Cedar Drift · 2 sprays")).toBeInTheDocument();

    await user.click(within(shelf).getByRole("button", { name: "Remove Cedar Drift" }));
    expect(within(shelf).getByRole("button", { name: "Add Cedar Drift" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByText("Add a second bottle")).toBeInTheDocument();
  });

  it("keeps the flask's tilt and mode controls reachable by name", async () => {
    const user = userEvent.setup();
    render(<BlendStudio owned={owned} saved={[]} start={initialBlend({ ids: [owned[0].fragrance.id, owned[1].fragrance.id] })} />);
    const tilt = screen.getAllByRole("group", { name: "Tilt it" })[0];
    await user.click(within(tilt).getByRole("button", { name: "Warmer" }));
    expect(within(tilt).getByRole("button", { name: "Warmer" })).toHaveAttribute("aria-pressed", "true");
    await user.click(within(tilt).getByRole("button", { name: "Warmer" }));
    expect(within(tilt).getByRole("button", { name: "Warmer" })).toHaveAttribute("aria-pressed", "false");
  });

  it("offers the empty room when fewer than two bottles are owned", () => {
    render(<BlendStudio owned={owned.slice(0, 1)} saved={[]} start={initialBlend()} />);
    expect(screen.getByRole("heading", { name: "Add fragrances to your shelf to start blending" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Collection" })).toHaveAttribute("href", "/collection");
  });
});

describe("BlendStudio saving and wearing", () => {
  beforeEach(() => { vi.clearAllMocks(); });
  const ids = [owned[0].fragrance.id, owned[1].fragrance.id];
  const saved = (id: string, members: string[]) => ({ id, name: "Amber Dusk", notes: null, wear_count: 0, average_rating: null, last_worn_at: null, created_at: "2026-11-01T00:00:00Z", suggestion: { items: members.map((fragrance, index) => ({ fragrance: owned.find((item) => item.fragrance.id === fragrance)!.fragrance, role: "anchor", application_order: index + 1, suggested_sprays: 1 })), mode: "balanced", goal: null } }) as unknown as import("@/types/layering").SavedLayeringStack;

  it("saves the flask under a generated name and reports the save", async () => {
    const user = userEvent.setup();
    layering.saveLayerStack.mockResolvedValue({ id: "new-blend" });
    render(<BlendStudio owned={owned} saved={[]} start={initialBlend({ ids })} />);
    await waitFor(() => expect(screen.getByText("Strong fit")).toBeInTheDocument(), { timeout: 2000 });
    await user.click(screen.getByRole("button", { name: "Save blend" }));
    const dialog = await screen.findByRole("dialog", { name: "Save blend" });
    expect((within(dialog).getByLabelText("Name") as HTMLInputElement).value).toMatch(/^\S+ \S+$/);
    await user.click(within(dialog).getByRole("button", { name: "Save blend" }));
    await waitFor(() => expect(layering.saveLayerStack).toHaveBeenCalledWith(ids, "balanced", null, expect.any(String), undefined));
  });

  it("offers the existing blend instead of saving an identical one", async () => {
    const user = userEvent.setup();
    render(<BlendStudio owned={owned} saved={[saved("existing-blend", ids)]} start={initialBlend({ ids })} />);
    await waitFor(() => expect(screen.getByText("Strong fit")).toBeInTheDocument(), { timeout: 2000 });
    await user.click(screen.getByRole("button", { name: "Save blend" }));
    const dialog = await screen.findByRole("dialog", { name: "Save blend" });
    expect(within(dialog).getByText(/already saved this blend as/)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Open it" })).toBeInTheDocument();
    expect(layering.saveLayerStack).not.toHaveBeenCalled();
  });

  it("saves and wears an unsaved blend, then rates the wear", async () => {
    const user = userEvent.setup();
    layering.saveLayerStack.mockResolvedValue({ id: "new-blend" });
    layering.logLayerStackWear.mockResolvedValue({ id: "wear-1", stack_id: "new-blend", rating: null, notes: null, worn_at: "2026-11-14T12:00:00Z" });
    layering.rateLayerStackWear.mockResolvedValue({ id: "wear-1" });
    render(<BlendStudio owned={owned} saved={[]} start={initialBlend({ ids })} />);
    await waitFor(() => expect(screen.getByText("Strong fit")).toBeInTheDocument(), { timeout: 2000 });
    await user.click(screen.getByRole("button", { name: "Save and wear" }));
    const dialog = await screen.findByRole("dialog", { name: "Save and wear" });
    await user.click(within(dialog).getByRole("button", { name: "Save and wear" }));
    await waitFor(() => expect(layering.logLayerStackWear).toHaveBeenCalledWith("new-blend", null, ""));
    const ratings = await screen.findByRole("dialog", { name: "How did it wear?" });
    await user.click(within(ratings).getByRole("button", { name: "Rate 4 of 5" }));
    await waitFor(() => expect(layering.rateLayerStackWear).toHaveBeenCalledWith("new-blend", "wear-1", 4));
  });
});
