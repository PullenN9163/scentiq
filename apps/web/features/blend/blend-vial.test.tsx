import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fragranceSummary } from "@/test/catalog-fixtures";
import type { SavedLayeringStack } from "@/types/layering";

import { BlendVial } from "./blend-vial";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }) }));
const layering = vi.hoisted(() => ({ renameLayerStack: vi.fn(), deleteLayerStack: vi.fn(), logLayerStackWear: vi.fn(), getLayerStackHistory: vi.fn() }));
vi.mock("@/lib/server/layering-actions", () => layering);

const stackId = "aaaaaaaa-0000-4000-8000-000000000001";
const stack = {
  id: stackId, name: "Amber Dusk", notes: null, wear_count: 2, average_rating: 4.5, last_worn_at: "2026-11-10T12:00:00Z", created_at: "2026-11-01T00:00:00Z",
  suggestion: { items: [
    { fragrance: fragranceSummary({ id: "f1", name: "By the Fireplace", top_accords: ["Amber"] }), role: "anchor", application_order: 1, suggested_sprays: 2 },
    { fragrance: fragranceSummary({ id: "f2", name: "Cedar Drift", top_accords: ["Woody"] }), role: "accent", application_order: 2, suggested_sprays: 1 },
  ], mode: "balanced" },
} as unknown as SavedLayeringStack;

beforeEach(() => {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: false, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  layering.renameLayerStack.mockResolvedValue({});
  layering.deleteLayerStack.mockResolvedValue(undefined);
  layering.getLayerStackHistory.mockResolvedValue([{ id: "w1", notes: null, rating: null, stack_id: stackId, worn_at: "2026-11-10T12:00:00Z" }]);
});
afterEach(() => { vi.clearAllMocks(); vi.unstubAllGlobals(); });

describe("BlendVial vault actions", () => {
  it("names the blend, its members and when it was last worn", () => {
    render(<BlendVial stack={stack} />);
    expect(screen.getByRole("link", { name: /Amber Dusk/ })).toHaveAttribute("href", `/layering?saved=${stackId}`);
    expect(screen.getByText(/worn 2×/)).toHaveTextContent("By the Fireplace + Cedar Drift · worn 2×");
    expect(screen.getByText(/Last worn/)).toBeInTheDocument();
  });

  it("renames through renameLayerStack with the trimmed name", async () => {
    const user = userEvent.setup();
    render(<BlendVial stack={stack} />);
    await user.click(screen.getByRole("button", { name: "More actions for Amber Dusk" }));
    await user.click(await screen.findByRole("menuitem", { name: "Rename" }));
    const field = await screen.findByLabelText("Name");
    await user.clear(field);
    await user.type(field, "  Velvet Noon  ");
    await user.click(screen.getByRole("button", { name: "Save name" }));
    await waitFor(() => expect(layering.renameLayerStack).toHaveBeenCalledWith(stackId, "Velvet Noon"));
  });

  it("deletes only after the confirm step, through deleteLayerStack", async () => {
    const user = userEvent.setup();
    render(<BlendVial stack={stack} />);
    await user.click(screen.getByRole("button", { name: "More actions for Amber Dusk" }));
    await user.click(await screen.findByRole("menuitem", { name: "Delete" }));
    expect(layering.deleteLayerStack).not.toHaveBeenCalled();
    const dialog = await screen.findByRole("dialog", { name: "Delete Amber Dusk?" });
    await user.click(within(dialog).getByRole("button", { name: "Delete blend" }));
    await waitFor(() => expect(layering.deleteLayerStack).toHaveBeenCalledWith(stackId));
  });

  it("shows the wear history from getLayerStackHistory without an unrated label", async () => {
    const user = userEvent.setup();
    render(<BlendVial stack={stack} />);
    await user.click(screen.getByRole("button", { name: "More actions for Amber Dusk" }));
    await user.click(await screen.findByRole("menuitem", { name: "Wear history" }));
    await waitFor(() => expect(layering.getLayerStackHistory).toHaveBeenCalledWith(stackId));
    const dialog = await screen.findByRole("dialog", { name: "Amber Dusk: wear history" });
    expect(within(dialog).getByRole("list")).toBeInTheDocument();
    expect(within(dialog).queryByText(/Not recorded|unknown/)).toBeNull();
  });
});
