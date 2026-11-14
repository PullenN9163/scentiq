import { describe, expect, it } from "vitest";

import { fragranceSummary } from "@/test/catalog-fixtures";
import type { CollectionItem } from "@/types/api";
import type { SavedLayeringStack } from "@/types/layering";

import { blendStartFromQuery, shelfOrder } from "./blend-start";

const ids = ["11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222", "33333333-3333-4333-8333-333333333333"];

function owned(id: string, name: string, rating: number | null = null): CollectionItem {
  return { id: `item-${id}`, fragrance: fragranceSummary({ id, name }), ownership_type: "bottle", status: "owned", bottle_size_ml: 100, remaining_ml: 50, user_rating: rating, purchase_price: null, purchase_date: null, custom_longevity: null, custom_projection: null };
}
const shelf = [owned(ids[0], "Cedar", 3), owned(ids[1], "Lemon", 5), owned(ids[2], "Unrated")];

function saved(members: string[], mode: "balanced" | "safe" = "balanced"): SavedLayeringStack {
  return {
    id: "aaaaaaaa-0000-4000-8000-000000000001", name: "Amber Dusk", notes: null, wear_count: 0, average_rating: null, last_worn_at: null, created_at: "2026-11-01T00:00:00Z",
    suggestion: { items: members.map((id, index) => ({ fragrance: fragranceSummary({ id }), role: "anchor", application_order: index + 1, suggested_sprays: 1 })), mode, goal: "warmer" },
  } as unknown as SavedLayeringStack;
}

describe("shelfOrder", () => {
  it("puts the most rated first and unrated last", () => {
    expect(shelfOrder(shelf).map((item) => item.fragrance.name)).toEqual(["Lemon", "Cedar", "Unrated"]);
  });
});

describe("blendStartFromQuery", () => {
  it("pours the anchor from a=", () => {
    const load = blendStartFromQuery({ a: ids[1] }, shelf, []);
    expect(load).toEqual({ start: { ids: [ids[1]], mode: "balanced", goal: null, savedId: null, suggestion: null }, evaluate: false });
  });

  it("ignores a= for a bottle the member does not own", () => {
    expect(blendStartFromQuery({ a: "99999999-9999-4999-8999-999999999999" }, shelf, []).start.ids).toEqual([]);
  });

  it("loads a stack from stack=, mode= and goal= and asks for a first reading", () => {
    const load = blendStartFromQuery({ stack: `${ids[0]},${ids[2]}`, mode: "contrast", goal: "darker" }, shelf, []);
    expect(load.evaluate).toBe(true);
    expect(load.start).toEqual({ ids: [ids[0], ids[2]], mode: "contrast", goal: "darker", savedId: null, suggestion: null });
  });

  it("rejects an invalid stack (duplicate, too many, not owned)", () => {
    expect(blendStartFromQuery({ stack: `${ids[0]},${ids[0]}` }, shelf, []).start.ids).toEqual([]);
    expect(blendStartFromQuery({ stack: `${ids[0]},${ids[1]},${ids[2]},${ids[0]}` }, shelf, []).evaluate).toBe(false);
    expect(blendStartFromQuery({ stack: `${ids[0]},99999999-9999-4999-8999-999999999999` }, shelf, []).evaluate).toBe(false);
  });

  it("loads a saved blend from saved= with its mode, goal and reading", () => {
    const stack = saved([ids[0], ids[1]], "safe");
    const load = blendStartFromQuery({ saved: stack.id }, shelf, [stack]);
    expect(load.evaluate).toBe(false);
    expect(load.start.ids).toEqual([ids[0], ids[1]]);
    expect(load.start.mode).toBe("safe");
    expect(load.start.goal).toBe("warmer");
    expect(load.start.savedId).toBe(stack.id);
    expect(load.start.suggestion).toBe(stack.suggestion);
  });

  it("re-reads a saved blend when one of its bottles is no longer owned", () => {
    const stack = saved([ids[0], ids[1]]);
    const load = blendStartFromQuery({ saved: stack.id }, [shelf[0]], [stack]);
    expect(load.start.ids).toEqual([ids[0]]);
    expect(load.evaluate).toBe(false);
    expect(load.start.suggestion).toBeNull();
  });

  it("falls back to an empty flask for unknown or missing parameters", () => {
    expect(blendStartFromQuery({ saved: "nope" }, shelf, []).start.ids).toEqual([]);
    expect(blendStartFromQuery({ mode: "wild", goal: "bogus" }, shelf, []).start).toEqual({ ids: [], mode: "balanced", goal: null, savedId: null, suggestion: null });
  });
});
