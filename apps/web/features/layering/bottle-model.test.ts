import { describe, expect, it } from "vitest";
import { bandStarts, bottleDescription, bottleSegments } from "./bottle-model";

const stack = {
  score_percent: 82,
  items: [
    { fragrance: { id: "a", name: "Anchor" }, suggested_sprays: 2 },
    { fragrance: { id: "b", name: "Bridge" }, suggested_sprays: 1 },
    { fragrance: { id: "c", name: "Accent" }, suggested_sprays: 1 },
  ],
} as never;

describe("bottle model", () => {
  it("sizes liquid bands by spray share and stacks them from the base", () => {
    const segments = bottleSegments(stack);
    expect(segments.map((s) => s.share)).toEqual([0.5, 0.25, 0.25]);
    expect(segments.reduce((sum, s) => sum + s.share, 0)).toBeCloseTo(1);
    expect(bandStarts(segments)).toEqual([0, 0.5, 0.75]);
  });
  it("keeps colours stable per fragrance and describes the blend for assistive tech", () => {
    expect(bottleSegments(stack)[0].color).toBe(bottleSegments(stack)[0].color);
    expect(bottleDescription(stack)).toContain("82% match");
    expect(bottleDescription(stack)).toContain("Anchor 50%");
  });
});
