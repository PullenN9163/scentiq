import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { evaluateLayerStack } from "@/lib/server/layering-actions";
import type { LayeringStackSuggestion } from "@/types/layering";

import { blendReducer, initialBlend, type BlendAction, type BlendState } from "./blend-state";
import { EVALUATE_DELAY_MS, useBlendEvaluation } from "./use-blend-evaluation";

vi.mock("@/lib/server/layering-actions", () => ({ evaluateLayerStack: vi.fn() }));
const evaluate = vi.mocked(evaluateLayerStack);

function reply(verdict: string): LayeringStackSuggestion {
  return { items: [], verdict, score: 0.5 } as unknown as LayeringStackSuggestion;
}

function setup(initial: Partial<BlendState> & { ids: string[] }) {
  const dispatched: BlendAction[] = [];
  let state: BlendState = { ...initialBlend({ ids: initial.ids }), ...initial };
  const dispatch = (action: BlendAction) => {
    dispatched.push(action);
    state = blendReducer(state, action);
  };
  const hook = renderHook(({ current }: { current: BlendState }) => useBlendEvaluation(current, dispatch), { initialProps: { current: state } });
  return { hook, dispatched, current: () => state, rerender: (next: BlendState) => { state = next; hook.rerender({ current: next }); } };
}

beforeEach(() => { vi.useFakeTimers(); evaluate.mockReset(); });
afterEach(() => { vi.useRealTimers(); });

describe("useBlendEvaluation", () => {
  it("waits 250ms after the last change, then reads the blend once", async () => {
    const env = setup({ ids: ["a", "b"] });
    evaluate.mockResolvedValue(reply("Strong fit"));
    await act(async () => { vi.advanceTimersByTime(EVALUATE_DELAY_MS - 1); });
    expect(evaluate).not.toHaveBeenCalled();
    await act(async () => { vi.advanceTimersByTime(1); });
    expect(evaluate).toHaveBeenCalledWith(["a", "b"], "balanced", null);
    expect(env.current().suggestion?.verdict).toBe("Strong fit");
  });

  it("does not read a blend with fewer than two bottles", async () => {
    setup({ ids: ["a"] });
    await act(async () => { vi.advanceTimersByTime(1000); });
    expect(evaluate).not.toHaveBeenCalled();
  });

  it("skips the first reading when a suggestion is already supplied", async () => {
    const dispatch = vi.fn();
    const base = { ...initialBlend({ ids: ["a", "b"] }), suggestion: reply("Strong fit") };
    renderHook(() => useBlendEvaluation(base, dispatch, true));
    await act(async () => { vi.advanceTimersByTime(1000); });
    expect(evaluate).not.toHaveBeenCalled();
  });

  it("re-reads when the tilt or mode changes, and ignores the older reply", async () => {
    let resolveFirst: (value: LayeringStackSuggestion) => void = () => {};
    evaluate.mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve; }));
    evaluate.mockResolvedValueOnce(reply("Promising blend"));
    const env = setup({ ids: ["a", "b"] });
    await act(async () => { vi.advanceTimersByTime(EVALUATE_DELAY_MS); });
    env.rerender({ ...env.current(), goal: "warmer" });
    await act(async () => { vi.advanceTimersByTime(EVALUATE_DELAY_MS); });
    expect(evaluate).toHaveBeenLastCalledWith(["a", "b"], "balanced", "warmer");
    await act(async () => { resolveFirst(reply("Tricky balance")); });
    expect(env.current().suggestion?.verdict).toBe("Promising blend");
  });
});
