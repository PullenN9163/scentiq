import { describe, expect, it } from "vitest";

import { ACCORD_KEYS } from "@/lib/accord";

import { ACCORD_WORDS, TIME_WORDS, generateBlendName } from "./blend-names";

describe("generateBlendName", () => {
  it("has at least twelve time words and two words for every accord", () => {
    expect(TIME_WORDS.length).toBeGreaterThanOrEqual(12);
    for (const key of ACCORD_KEYS) expect(ACCORD_WORDS[key]).toHaveLength(2);
  });

  it("names a blend from its strongest accord and a time word", () => {
    expect(generateBlendName(["amber", "green"], () => 0)).toBe("Amber Dusk");
    expect(generateBlendName(["green"], () => 0.99)).toBe("Fern Midnight");
  });

  it("falls back to neutral words with no accords", () => {
    expect(generateBlendName([], () => 0)).toBe("Quiet Dusk");
  });

  it("uses the second accord's words half the time", () => {
    const sequence = [0.9, 0, 0];
    expect(generateBlendName(["woody", "fresh"], () => sequence.shift() ?? 0)).toBe("Silver Dusk");
  });
});
