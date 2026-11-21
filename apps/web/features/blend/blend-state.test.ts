import { describe, expect, it } from "vitest";

import type { LayeringStackSuggestion } from "@/types/layering";

import { blendReducer, initialBlend, sameBlend, suggestionMatches, type BlendState } from "./blend-state";

function reading(ids: string[]): LayeringStackSuggestion {
  return {
    items: ids.map((id, index) => ({ fragrance: { id } as LayeringStackSuggestion["items"][number]["fragrance"], role: "anchor", application_order: index + 1, suggested_sprays: 1 })),
    mode: "balanced", score: 0.7, verdict: "Strong fit",
  } as unknown as LayeringStackSuggestion;
}

function start(ids: string[] = []): BlendState {
  return initialBlend({ ids });
}

describe("blendReducer", () => {
  it("adds bottles up to three and replaces the oldest for a fourth", () => {
    let state = start();
    for (const id of ["a", "b", "c", "d"]) state = blendReducer(state, { type: "add", id });
    expect(state.ids).toEqual(["b", "c", "d"]);
    expect(state.lastAdded).toBe("d");
  });

  it("ignores a duplicate add and removes on toggle", () => {
    const state = start(["a", "b"]);
    expect(blendReducer(state, { type: "add", id: "a" })).toBe(state);
    expect(blendReducer(state, { type: "toggle", id: "a" }).ids).toEqual(["b"]);
    expect(blendReducer(state, { type: "toggle", id: "z" }).ids).toEqual(["a", "b", "z"]);
  });

  it("tapping the selected tilt clears it", () => {
    const warm = blendReducer(start(["a", "b"]), { type: "goal", goal: "warmer" });
    expect(warm.goal).toBe("warmer");
    expect(blendReducer(warm, { type: "goal", goal: "warmer" }).goal).toBeNull();
    expect(blendReducer(warm, { type: "goal", goal: "darker" }).goal).toBe("darker");
  });

  it("undoes the last change in one step", () => {
    const before = start(["a", "b"]);
    const changed = blendReducer(before, { type: "mode", mode: "contrast" });
    expect(changed.mode).toBe("contrast");
    const undone = blendReducer(changed, { type: "undo" });
    expect(undone.mode).toBe("balanced");
    expect(undone.ids).toEqual(["a", "b"]);
    expect(blendReducer(undone, { type: "undo" })).toEqual(undone);
  });

  it("drops the reading when fewer than two bottles remain", () => {
    const read = { ...start(["a", "b"]), suggestion: reading(["a", "b"]), status: "idle" as const };
    expect(blendReducer(read, { type: "remove", id: "b" }).suggestion).toBeNull();
  });

  it("ignores stale evaluation responses", () => {
    let state = blendReducer(start(["a", "b"]), { type: "evaluating", request: 2 });
    const stale = blendReducer(state, { type: "evaluated", request: 1, suggestion: reading(["x"]) });
    expect(stale.suggestion).toBeNull();
    state = blendReducer(state, { type: "evaluated", request: 2, suggestion: reading(["a", "b"]) });
    expect(state.status).toBe("idle");
    expect(state.suggestion?.verdict).toBe("Strong fit");
  });

  it("marks only the current request as failed", () => {
    const state = blendReducer(start(["a", "b"]), { type: "evaluating", request: 3 });
    expect(blendReducer(state, { type: "failed", request: 2 }).status).toBe("evaluating");
    expect(blendReducer(state, { type: "failed", request: 3 }).status).toBe("error");
  });

  it("loads a snapshot and remembers the previous flask for undo", () => {
    const loaded = blendReducer(start(["a", "b"]), { type: "load", ids: ["c", "d"], mode: "safe", goal: "fresher" });
    expect(loaded.ids).toEqual(["c", "d"]);
    expect(loaded.mode).toBe("safe");
    expect(blendReducer(loaded, { type: "undo" }).ids).toEqual(["a", "b"]);
  });
});

describe("suggestionMatches and sameBlend", () => {
  it("matches a reading to the bottles in the flask regardless of order", () => {
    const state = { ...start(["b", "a"]), suggestion: reading(["a", "b"]) };
    expect(suggestionMatches(state)).toBe(true);
    expect(suggestionMatches({ ...state, ids: ["a", "c"] })).toBe(false);
  });

  it("compares saved blends without order, mode or goal sensitivity to nulls", () => {
    expect(sameBlend({ ids: ["a", "b"], mode: "balanced", goal: null }, { ids: ["b", "a"], mode: "balanced", goal: null })).toBe(true);
    expect(sameBlend({ ids: ["a", "b"], mode: "balanced", goal: null }, { ids: ["a", "b"], mode: "safe", goal: null })).toBe(false);
  });
});
