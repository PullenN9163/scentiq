import { describe, expect, it } from "vitest";

import { layerHeights, layerTops, type FlaskLayer } from "./flask";

const layers: FlaskLayer[] = [
  { id: "a", accord: "woody", sprays: 2 },
  { id: "b", accord: "amber", sprays: 1 },
];

describe("flask geometry", () => {
  it("splits the fill by spray share, bottom layer first", () => {
    expect(layerHeights(layers)).toEqual([2 / 3, 1 / 3]);
  });

  it("places each layer's top edge from the foot of the flask upward", () => {
    // Fill runs from y 104 (top) to 260 (foot): 156 units.
    const [bottom, top] = layerTops(layers, 1);
    expect(bottom).toBeCloseTo(260 - (2 / 3) * 156);
    expect(top).toBeCloseTo(104);
  });

  it("shrinks the fill for a single bottle and handles no sprays", () => {
    expect(layerTops([{ id: "a", accord: "fresh", sprays: 1 }], 0.4)[0]).toBeCloseTo(260 - 0.4 * 156);
    expect(layerHeights([{ id: "a", accord: "fresh", sprays: 0 }, { id: "b", accord: "fresh", sprays: 0 }])).toEqual([0.5, 0.5]);
  });
});
