import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fragranceSummary } from "@/test/catalog-fixtures";
import type { LayeringStackSuggestion } from "@/types/layering";
import { LayeringLab } from "./layering-lab";
import { LayeringStudioCanvas } from "./layering-studio-canvas";

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
const fourth = fragranceSummary({
  id: "44444444-4444-4444-8444-444444444444",
  name: "Velvet woods",
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
  it("announces the completed ScentIQ score after analysis", () => {
    render(
      <LayeringLab
        owned={[first, second]}
        initialIntelligence={{ ...page, supported_goals: [...page.supported_goals] }}
      />,
    );

    expect(screen.getByRole("status", { name: "ScentIQ score update" })).toHaveTextContent(
      "ScentIQ score 70. Promising blend",
    );
  });

  it("marks reduced-motion canvases while keeping the composition available", () => {
    render(
      <LayeringStudioCanvas
        items={stack.items}
        composition={stack}
        pending={false}
        reducedMotion
        focusedId={null}
        onFocus={() => undefined}
        onMove={() => undefined}
        onRemove={() => undefined}
        onReplace={() => undefined}
        onAdd={() => undefined}
      />,
    );

    const canvas = screen.getByRole("region", { name: "Interactive blend canvas" });
    expect(canvas).toHaveAttribute("data-motion", "reduced");
    expect(screen.getAllByTestId("canvas-bottle")).toHaveLength(2);
  });

  it("keeps the canvas and bottles present while a blend is being analyzed", async () => {
    let finish: (value: LayeringStackSuggestion) => void = () => undefined;
    actions.evaluateLayerStack.mockImplementationOnce(
      () => new Promise<LayeringStackSuggestion>((resolve) => { finish = resolve; }),
    );
    render(
      <LayeringLab
        owned={[first, second]}
        initialIntelligence={{ ...page, supported_goals: [...page.supported_goals] }}
        initialStack={stack}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Make it fresher" }));
    const canvas = screen.getByRole("region", { name: "Interactive blend canvas" });
    expect(canvas).toHaveAttribute("aria-busy", "true");
    expect(within(canvas).getAllByTestId("canvas-bottle")).toHaveLength(2);

    finish({ ...stack, goal: "fresher" });
    await waitFor(() => expect(canvas).toHaveAttribute("aria-busy", "false"));
  });

  it("keeps keyboard focus on the selected session blend", async () => {
    render(
      <LayeringLab
        owned={[first, second]}
        initialIntelligence={{ ...page, supported_goals: [...page.supported_goals] }}
        initialStack={stack}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "New blend" }));
    const draft = screen.getByRole("button", { name: /Promising blend.*70/ });
    await userEvent.click(draft);

    expect(draft).toHaveFocus();
    expect(draft).toHaveAttribute("aria-current", "true");
  });

  it("preserves the active draft when a different suggestion is adopted", async () => {
    const alternative: LayeringStackSuggestion = {
      ...stack,
      items: [
        {...stack.items[0], fragrance: second},
        {...stack.items[1], fragrance: third},
      ],
      verdict: "Bold experiment",
      score: 0.81,
    };
    actions.evaluateLayerStack.mockResolvedValue(alternative);
    render(
      <LayeringLab
        owned={[first, second, third]}
        initialIntelligence={{...page, suggestions:[alternative], supported_goals:[...page.supported_goals]}}
        initialStack={stack}
      />,
    );

    await userEvent.click(screen.getByRole("button", {name:"Try / edit stack"}));
    await userEvent.click(screen.getByRole("button", {name:"Make it warmer"}));

    const sessions = screen.getByRole("region", {name:"Session blends"});
    expect(await within(sessions).findByRole("button", {name:/Bold experiment.*81/})).toBeVisible();
    expect(within(sessions).getByRole("button", {name:/Promising blend.*70/})).toBeVisible();
  });

  it("ignores a late surprise response after explicit work begins", async () => {
    let finishSurprise: (value: unknown) => void = () => undefined;
    surfaceActions.surfaceChoice
      .mockResolvedValueOnce({ok:false,error:""})
      .mockImplementationOnce(() => new Promise((resolve) => { finishSurprise = resolve; }));
    const surprise = {...stack, verdict:"Late surprise", score:0.91};
    render(
      <LayeringLab
        owned={[first, second, third]}
        initialIntelligence={{...page,supported_goals:[...page.supported_goals]}}
      />,
    );
    await waitFor(() => expect(surfaceActions.surfaceChoice).toHaveBeenCalledTimes(1));
    await userEvent.click(await screen.findByRole("button", {name:"Surprise me"}));
    await userEvent.click(screen.getByRole("button", {name:"Refine this blend"}));
    finishSurprise({ok:true,data:{batch_id:"b",candidate_id:"c",selected:surprise,remaining_options:1,options_exhausted:false}});

    await waitFor(() => expect(surfaceActions.surfaceChoice).toHaveBeenCalledTimes(2));
    expect(screen.getByRole("region", {name:"Stack builder"})).toHaveTextContent(first.name);
    expect(screen.queryByRole("heading", {name:"Late surprise"})).not.toBeInTheDocument();
  });

  it("offers touch-safe bottle actions directly on the canvas", async () => {
    render(
      <LayeringLab
        owned={[first, second, third]}
        initialIntelligence={{...page,supported_goals:[...page.supported_goals]}}
        initialStack={stack}
      />,
    );

    await userEvent.click(screen.getByRole("button", {name:`Select ${second.name} on canvas`}));
    const tray = screen.getByRole("region", {name:`Actions for ${second.name}`});
    await waitFor(() => {
      expect(within(tray).getByRole("button", {name:`Move ${second.name} earlier`})).toBeVisible();
      expect(within(tray).getByRole("button", {name:`Replace ${second.name}`})).toBeVisible();
      expect(within(tray).getByRole("button", {name:`Remove ${second.name}`})).toBeVisible();
    });
    expect(screen.getByRole("button", {name:"Add fragrance to position 3"})).toBeVisible();
  });

  it("clears an unfinished replacement when the composition changes", async () => {
    const triple = {
      ...stack,
      items:[...stack.items,{fragrance:third,role:"bridge" as const,application_order:3,suggested_sprays:1}],
    };
    render(
      <LayeringLab
        owned={[first, second, third, fourth]}
        initialIntelligence={{...page,supported_goals:[...page.supported_goals]}}
        initialStack={triple}
      />,
    );
    await userEvent.click(screen.getByRole("button", {name:"Add Velvet woods"}));
    expect(screen.getByRole("region", {name:"Replace a fragrance"})).toBeVisible();
    await userEvent.click(screen.getByRole("button", {name:"New blend"}));
    expect(screen.queryByRole("region", {name:"Replace a fragrance"})).not.toBeInTheDocument();
  });

  it("renders the touch-first layering studio landmarks", () => {
    render(
      <LayeringLab
        owned={[first, second, third]}
        initialIntelligence={{ ...page, supported_goals: [...page.supported_goals] }}
      />,
    );

    expect(screen.getByRole("region", { name: "Layering studio" })).toBeVisible();
    expect(screen.getByRole("region", { name: "Interactive blend canvas" })).toBeVisible();
    expect(screen.getByRole("region", { name: "ScentIQ read" })).toBeVisible();
    expect(screen.getByRole("region", { name: "Your fragrance shelf" })).toBeVisible();
    expect(screen.getByRole("region", { name: "Session blends" })).toBeVisible();
  });

  it("asks which fragrance to replace when the canvas is full", async () => {
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
    };
    render(
      <LayeringLab
        owned={[first, second, third, fourth]}
        initialIntelligence={{ ...page, supported_goals: [...page.supported_goals] }}
        initialStack={triple}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Add Velvet woods" }));

    expect(screen.getByRole("region", { name: "Replace a fragrance" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Replace Fresh bridge" })).toBeVisible();
  });

  it("retains evaluated blends in the session when starting another", async () => {
    render(
      <LayeringLab
        owned={[first, second, third]}
        initialIntelligence={{ ...page, supported_goals: [...page.supported_goals] }}
        initialStack={stack}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "New blend" }));

    expect(
      within(screen.getByRole("region", { name: "Session blends" })).getByRole(
        "button",
        { name: /Promising blend.*70/ },
      ),
    ).toBeVisible();
  });

  it("restores an unsaved session blend", async () => {
    render(
      <LayeringLab
        owned={[first, second, third]}
        initialIntelligence={{ ...page, supported_goals: [...page.supported_goals] }}
        initialStack={stack}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "New blend" }));

    await userEvent.click(
      within(screen.getByRole("region", { name: "Session blends" })).getByRole(
        "button",
        { name: /Promising blend.*70/ },
      ),
    );

    expect(screen.getAllByTestId("stack-item")).toHaveLength(2);
    expect(screen.getByRole("region", { name: "Stack builder" })).toHaveTextContent(
      "Fresh bridge",
    );
  });

  it("preserves explicit stack ids when direction changes", async () => {
    actions.evaluateLayerStack.mockResolvedValue({ ...stack, goal: "warmer" });
    render(
      <LayeringLab
        owned={[first, second, third]}
        initialIntelligence={{ ...page, supported_goals: [...page.supported_goals] }}
        initialStack={stack}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Make it warmer" }));

    expect(actions.evaluateLayerStack).toHaveBeenCalledWith(
      [first.id, second.id],
      "balanced",
      "warmer",
    );
    expect(screen.getAllByTestId("stack-item")).toHaveLength(2);
  });

  it("ignores stale evaluations after a newer composition", async () => {
    let resolveOld: (value: LayeringStackSuggestion) => void = () => undefined;
    let resolveNew: (value: LayeringStackSuggestion) => void = () => undefined;
    actions.evaluateLayerStack
      .mockImplementationOnce(
        () => new Promise<LayeringStackSuggestion>((resolve) => { resolveOld = resolve; }),
      )
      .mockImplementationOnce(
        () => new Promise<LayeringStackSuggestion>((resolve) => { resolveNew = resolve; }),
      );
    render(
      <LayeringLab
        owned={[first, second, third]}
        initialIntelligence={{ ...page, supported_goals: [...page.supported_goals] }}
        initialStack={stack}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Make it fresher" }));
    fireEvent.click(screen.getByRole("button", { name: "Make it warmer" }));
    resolveNew({ ...stack, goal: "warmer", verdict: "Bold experiment", score: 0.92 });
    resolveOld({ ...stack, goal: "fresher", verdict: "Tricky balance", score: 0.2 });

    expect(await screen.findByRole("heading", { name: "Bold experiment" })).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Tricky balance" })).not.toBeInTheDocument();
  });

  it("shows a suggestion as a preview until the user adopts it", () => {
    render(
      <LayeringLab
        owned={[first, second, third]}
        initialIntelligence={{ ...page, supported_goals: [...page.supported_goals] }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Promising blend" })).toBeVisible();
    expect(screen.queryByRole("region", { name: "Stack builder" })).not.toBeInTheDocument();
    expect(
      within(screen.getByRole("region", { name: "Session blends" })).queryByRole("button", {
        name: /Promising blend/,
      }),
    ).not.toBeInTheDocument();
  });

  it("keeps a custom blend together and reevaluates it when the goal changes", async () => {
    actions.evaluateLayerStack.mockResolvedValue({...stack, goal:null, score:0.76, verdict:"Strong fit"});
    render(<LayeringLab owned={[first,second]} initialIntelligence={{...page,supported_goals:[...page.supported_goals]}} initialStack={{...stack,goal:"fresher"}} />);
    await userEvent.click(screen.getByRole("button", {name:"Keep it balanced"}));
    expect(actions.evaluateLayerStack).toHaveBeenCalledWith([first.id, second.id], "balanced", null);
    const stackBuilder = screen.getByRole("region", {name:"Stack builder"});
    expect(await within(stackBuilder).findByRole("heading", {name:"Strong fit"})).toBeVisible();
    expect(stackBuilder).toBeVisible();
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
    expect(screen.getByRole("button", {name:"Add Warm accent"})).toBeVisible();
    expect(screen.queryByRole("button", {name:`Add ${first.name}`})).not.toBeInTheDocument();
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
    expect(screen.getByRole("button", { name: `Add ${first.name}` })).toBeVisible();
    expect(screen.getByText("Build a scent with a point of view.")).toBeVisible();
    expect(screen.getAllByTestId("canvas-bottle")).toHaveLength(2);
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
