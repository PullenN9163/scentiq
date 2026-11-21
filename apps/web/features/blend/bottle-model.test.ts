import { describe, expect, it } from "vitest";
import { bandStarts, bottleDescription, bottleSegments } from "./bottle-model";

const layers = [
  { id: "a", accord: "woody", sprays: 2 },
  { id: "b", accord: "citrus", sprays: 1 },
  { id: "c", accord: "amber", sprays: 1 },
] as const;

describe("bottle model", () => {
  it("sizes liquid bands by spray share and stacks them from the base", () => {
    const segments = bottleSegments(layers, (accord) => `color-${accord}`);
    expect(segments.map((s) => s.share)).toEqual([0.5, 0.25, 0.25]);
    expect(segments[1].color).toBe("color-citrus");
    expect(bandStarts(segments)).toEqual([0, 0.5, 0.75]);
  });
  it("falls back to equal bands when no sprays are known", () => {
    const segments = bottleSegments(layers.map((l) => ({ ...l, sprays: 0 })), () => "#000");
    expect(segments.every((s) => Math.abs(s.share - 1 / 3) < 1e-9)).toBe(true);
  });
  it("describes the blend for assistive tech", () => {
    const stack = {
      score_percent: 82,
      items: [
        { fragrance: { name: "Anchor" } },
        { fragrance: { name: "Bridge" } },
        { fragrance: { name: "Accent" } },
      ],
    } as never;
    expect(bottleDescription(stack, layers)).toContain("82% match");
    expect(bottleDescription(stack, layers)).toContain("Anchor 50%");
    expect(bottleDescription(null, layers)).toBe("Cologne bottle");
  });
});
