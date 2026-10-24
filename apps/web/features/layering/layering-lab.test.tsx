import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
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
const surfaceActions = vi.hoisted(() => ({ surfaceChoice: vi.fn() }));
vi.mock("@/lib/server/layering-actions", () => actions);
vi.mock("@/lib/server/surface-choice-actions", () => surfaceActions);
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
  generation_mode: "baseline",
  algorithm_version: "layering-v3",
  verdict: "Promising blend",
  evidence_summary: "Some information missing",
  explanation: {
    why_they_fit: ["The scents share a soft woody thread."],
    what_changes: ["Fresh bridge adds a brighter citrus edge."],
    watch_out_for: ["Start light and adjust after it settles."],
  },
};
const page = {
  supported_goals: ["fresher", "warmer"] as const,
  suggestions: [stack],
  saved: [],
};
beforeEach(() => {
  Object.values(actions).forEach((action) => action.mockReset());
  surfaceActions.surfaceChoice.mockReset();
  surfaceActions.surfaceChoice.mockResolvedValue({ok:false,error:""});
  actions.getLayeringIntelligence.mockResolvedValue(page);
  actions.evaluateLayerStack.mockResolvedValue(stack);
});

describe("LayeringLab intelligence", () => {
  it("keeps a custom blend together and reevaluates it when the goal changes", async () => {
    actions.evaluateLayerStack.mockResolvedValue({...stack, goal:null, score:0.76, verdict:"Strong fit"});
    render(<LayeringLab owned={[first,second]} initialIntelligence={{...page,supported_goals:[...page.supported_goals]}} initialStack={{...stack,goal:"fresher"}} />);
    await userEvent.click(screen.getByRole("button", {name:"Keep it balanced"}));
    expect(actions.evaluateLayerStack).toHaveBeenCalledWith([first.id, second.id], "balanced", null);
    expect(await screen.findByRole("heading", {name:"Strong fit"})).toBeVisible();
    expect(screen.getByRole("region", {name:"Stack builder"})).toBeVisible();
  });
  it("does not let restored surprise options replace a blend the user is editing", async () => {
    surfaceActions.surfaceChoice
      .mockResolvedValueOnce({ok:false,error:""})
      .mockResolvedValueOnce({
        ok:true,
        data:{batch_id:"batch",selected:stack,candidate_id:"candidate",remaining_options:1,options_exhausted:false},
      });
    render(<LayeringLab owned={[first,second,third]} initialIntelligence={{...page,supported_goals:[...page.supported_goals]}} />);
    await waitFor(() => expect(surfaceActions.surfaceChoice).toHaveBeenCalledTimes(1));
    await userEvent.click(screen.getByRole("button", {name:"Refine this blend"}));
    await userEvent.click(screen.getByRole("button", {name:"Make it fresher"}));
    await waitFor(() => expect(actions.evaluateLayerStack).toHaveBeenCalledWith([first.id,second.id],"balanced","fresher"));
    expect(surfaceActions.surfaceChoice).toHaveBeenCalledTimes(1);
    expect(screen.getAllByTestId("stack-item")).toHaveLength(2);
  });
  it("explains the score in plain language and separates evidence confidence", () => {
    render(<LayeringLab owned={[first,second]} initialIntelligence={{...page,supported_goals:[...page.supported_goals]}} />);
    const stage = screen.getByRole("region", {name:"Fragrance composition"});
    expect(within(stage).getByRole("heading", {name:"Promising blend"})).toBeVisible();
    expect(within(stage).getByText("70 out of 100")).toBeVisible();
    expect(within(stage).getByText("Some information missing")).toBeVisible();
    const explanation = screen.getByRole("region", {name:"Blend explanation"});
    expect(within(explanation).getByRole("heading", {name:"Why they fit"})).toBeVisible();
    expect(within(explanation).getByText("The scents share a soft woody thread.")).toBeVisible();
  });
  it("filters a large collection by fragrance or house", async () => {
    render(<LayeringLab owned={[first,second,third]} initialIntelligence={{...page,supported_goals:[...page.supported_goals]}} />);
    await userEvent.type(screen.getByRole("searchbox", {name:"Search your collection"}), "Warm");
    expect(screen.getByRole("button", {name:"Choose anchor Warm accent"})).toBeVisible();
    expect(screen.queryByRole("button", {name:`Choose anchor ${first.name}`})).not.toBeInTheDocument();
  });
  it("keeps the edited ingredients without restoring a stale score after evaluation fails", async () => {
    actions.evaluateLayerStack.mockRejectedValueOnce(new Error("offline"));
    render(<LayeringLab owned={[first,second,third]} initialIntelligence={{...page,supported_goals:[...page.supported_goals]}} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", {name:"Refine this blend"}));
    await user.click(within(screen.getByRole("region", {name:"Stack builder"})).getByRole("button", {name:"Add Warm accent"}));
    expect(await screen.findByRole("alert")).toBeVisible();
    const stage = screen.getByRole("region", {name:"Fragrance composition"});
    expect(within(stage).queryByText("70%")).not.toBeInTheDocument();
    expect(within(stage).getAllByText("Warm accent")[0]).toBeVisible();
  });
  it("shows the actual suggested composition and opens its existing editor from the visual stage",async()=>{
    render(<LayeringLab owned={[first,second,third]} initialIntelligence={{...page,supported_goals:[...page.supported_goals]}}/>);
    const stage=screen.getByRole("region",{name:"Fragrance composition"});
    expect(within(stage).getAllByText(first.name)[0]).toBeVisible();
    expect(within(stage).getAllByText(second.name)[0]).toBeVisible();
    await userEvent.click(within(stage).getByRole("button",{name:"Refine this blend"}));
    expect(screen.getByRole("region",{name:"Stack builder"})).toBeVisible();
    expect(screen.getAllByTestId("stack-item")).toHaveLength(2);
  });
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
    expect(screen.getAllByText("Some information missing")[0]).toBeVisible();
  });
  it("updates suggestions when the supported goal changes", async () => {
    const user = userEvent.setup();
    actions.getLayeringIntelligence.mockResolvedValue({
      ...page,
      suggestions: [
        {
          ...stack,
          goal: "fresher",
          explanation: {...stack.explanation, why_they_fit:["Fresh citrus support"]},
        },
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
    expect(await within(builder).findByText("Ties them together")).toBeVisible();
    expect(
      within(builder).queryByRole("button", { name: `Add ${first.name}` }),
    ).not.toBeInTheDocument();
    const moveEarlier=within(builder).getByRole("button", { name: "Move Warm accent earlier" });
    // Evaluation renders its result before the transition releases controls.
    await waitFor(()=>expect(moveEarlier).toBeEnabled());
    await user.click(moveEarlier);
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
    const wearButton = screen.getByRole("button", { name: "Wear Bright morning" });
    await waitFor(() => expect(wearButton).toBeEnabled());
    await user.click(wearButton);
    await user.selectOptions(screen.getByLabelText("Personal rating"), "5");
    await user.type(screen.getByLabelText("Wear notes"), "Lovely");
    await user.click(screen.getByRole("button", { name: "Log this wear" }));
    expect(await screen.findByText("Wear logged")).toBeVisible();
    const historyButton = screen.getByRole("button", { name: "History for Bright morning" });
    await waitFor(() => expect(historyButton).toBeEnabled());
    await user.click(historyButton);
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
