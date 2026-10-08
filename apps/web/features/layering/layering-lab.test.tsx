import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fragranceSummary } from "@/test/catalog-fixtures";
import type { LayeringStackSuggestion } from "@/types/layering";
import { LayeringLab } from "./layering-lab";

const actions = vi.hoisted(() => ({
  getLayeringIntelligence: vi.fn(),
  evaluateLayerStack: vi.fn(),
  saveLayerStack: vi.fn(),
  renameLayerStack: vi.fn(),
  deleteLayerStack: vi.fn(),
  logLayerStackWear: vi.fn(),
  getLayerStackHistory: vi.fn(),
  rateLayerStackWear: vi.fn(),
}));
vi.mock("@/lib/server/layering-actions", () => actions);
vi.mock("@/lib/server/actions", () => ({
  getLayeringPair: vi.fn().mockResolvedValue(null),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
afterEach(cleanup);
const first = fragranceSummary();
const second = fragranceSummary({
  id: "22222222-2222-4222-8222-222222222222",
  name: "Fresh bridge",
});
const third = fragranceSummary({
  id: "33333333-3333-4333-8333-333333333333",
  name: "Warm accent",
});
const stack: LayeringStackSuggestion = {
  items: [
    {
      fragrance: first,
      role: "anchor",
      application_order: 1,
      suggested_sprays: 2,
    },
    {
      fragrance: second,
      role: "accent",
      application_order: 2,
      suggested_sprays: 1,
    },
  ],
  mode: "balanced",
  goal: null,
  score: 0.7,
  score_components: {
    bridge: 0.5,
    complement: 0.5,
    season_context: 0.8,
    projection_balance: 0.8,
    longevity_balance: 0.8,
    novelty: 0.5,
    user_affinity: 0.5,
    redundancy_penalty: 0.2,
    overload_penalty: 0,
  },
  shared_notes: ["cedar"],
  shared_accords: ["woody"],
  bridge_signals: ["cedar"],
  complementary_signals: ["citrus"],
  best_contexts: ["summer"],
  reasons: ["Recorded woody bridge", "Rule-based starting guidance"],
  warnings: [],
  total_sprays: 3,
  evidence_coverage: 0.8,
  evidence_label: "partial",
  algorithm_version: "layering-v2",
};
const page = {
  supported_goals: ["fresher", "warmer"] as const,
  suggestions: [stack],
  saved: [],
};
beforeEach(() => {
  Object.values(actions).forEach((action) => action.mockReset());
  actions.getLayeringIntelligence.mockResolvedValue(page);
  actions.evaluateLayerStack.mockResolvedValue(stack);
});

describe("LayeringLab intelligence", () => {
  it("starts from one anchor and shows owned support with application guidance", () => {
    render(
      <LayeringLab
        owned={[first, second, third]}
        initialIntelligence={{
          ...page,
          supported_goals: [...page.supported_goals],
        }}
      />,
    );
    expect(
      screen.getByRole("button", { name: `Choose anchor ${first.name}` }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Build around this scent")).toBeVisible();
    expect(screen.getByText(/3 sprays/)).toBeVisible();
    expect(screen.getByText(/80% recorded evidence/)).toBeVisible();
  });
  it("updates suggestions when the supported goal changes", async () => {
    const user = userEvent.setup();
    actions.getLayeringIntelligence.mockResolvedValue({
      ...page,
      suggestions: [
        { ...stack, goal: "fresher", reasons: ["Fresh citrus support"] },
      ],
    });
    render(
      <LayeringLab
        owned={[first, second]}
        initialIntelligence={{
          ...page,
          supported_goals: [...page.supported_goals],
        }}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Make it fresher" }));
    expect(await screen.findByText("Fresh citrus support")).toBeVisible();
  });
  it("edits a triple, prevents duplicates, and supports accessible reorder", async () => {
    const user = userEvent.setup();
    const triple = {
      ...stack,
      items: [
        ...stack.items,
        {
          fragrance: third,
          role: "bridge" as const,
          application_order: 3,
          suggested_sprays: 1,
        },
      ],
      total_sprays: 4,
    };
    actions.evaluateLayerStack.mockResolvedValue(triple);
    render(
      <LayeringLab
        owned={[first, second, third]}
        initialIntelligence={{
          ...page,
          supported_goals: [...page.supported_goals],
        }}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Try / edit stack" }));
    const builder = screen.getByRole("region", { name: "Stack builder" });
    await user.click(
      within(builder).getByRole("button", { name: "Add Warm accent" }),
    );
    expect(await within(builder).findByText("bridge")).toBeVisible();
    expect(
      within(builder).queryByRole("button", { name: `Add ${first.name}` }),
    ).not.toBeInTheDocument();
    await user.click(
      within(builder).getByRole("button", { name: "Move Warm accent earlier" }),
    );
    expect(within(builder).getAllByTestId("stack-item")[1]).toHaveTextContent(
      "Warm accent",
    );
  });
  it("saves and logs a wear with rating and notes, then displays the updated history", async () => {
    const user = userEvent.setup();
    actions.saveLayerStack.mockResolvedValue({
      id: "saved",
      name: "Bright morning",
      notes: null,
      created_at: "2026-10-07T00:00:00Z",
      last_worn_at: null,
      average_rating: null,
      wear_count: 0,
      suggestion: stack,
    });
    actions.logLayerStackWear.mockResolvedValue({
      id: "wear",
      stack_id: "saved",
      worn_at: "2026-10-07T00:00:00Z",
      rating: 5,
      notes: "Lovely",
    });
    actions.getLayerStackHistory.mockResolvedValue([
      {
        id: "wear",
        stack_id: "saved",
        worn_at: "2026-10-07T00:00:00Z",
        rating: 5,
        notes: "Lovely",
      },
    ]);
    render(
      <LayeringLab
        owned={[first, second]}
        initialIntelligence={{
          ...page,
          supported_goals: [...page.supported_goals],
        }}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Save combination" }));
    await user.type(
      screen.getByLabelText("Combination name"),
      "Bright morning",
    );
    await user.click(
      screen.getByRole("button", { name: "Save named combination" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Bright morning" }),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Wear Bright morning" }),
    );
    await user.selectOptions(screen.getByLabelText("Personal rating"), "5");
    await user.type(screen.getByLabelText("Wear notes"), "Lovely");
    await user.click(screen.getByRole("button", { name: "Log this wear" }));
    expect(await screen.findByText("Wear logged")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "History for Bright morning" }),
    );
    expect(await screen.findByText("Lovely")).toBeVisible();
  }, 10000);
  it("requires two owned fragrances", () => {
    render(
      <LayeringLab
        owned={[first]}
        initialIntelligence={{
          supported_goals: [],
          suggestions: [],
          saved: [],
        }}
      />,
    );
    expect(screen.getByText("Add at least two owned fragrances")).toBeVisible();
  });
});
