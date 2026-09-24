import { describe, expect, it } from "vitest";

import { toneFor } from "./tone";

describe("toneFor", () => {
  it("returns the same colour for the same id", () => {
    expect(toneFor("11111111-1111-4111-8111-111111111111")).toBe(
      toneFor("11111111-1111-4111-8111-111111111111"),
    );
  });

  it("returns a hex colour", () => {
    expect(toneFor("any-id")).toMatch(/^#[0-9a-f]{6}$/);
  });

  it("handles an empty id without throwing", () => {
    expect(toneFor("")).toMatch(/^#[0-9a-f]{6}$/);
  });

  it("spreads different ids across the palette", () => {
    const tones = new Set(
      Array.from({ length: 40 }, (_, index) => toneFor(`fragrance-${index}`)),
    );

    // Not a uniformity guarantee, just that it is not collapsing to one colour.
    expect(tones.size).toBeGreaterThan(3);
  });
});
