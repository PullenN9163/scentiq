import { describe, expect, it } from "vitest";

import { accordFor, accordFromLabel, accordVars } from "./accord";

describe("accordFromLabel", () => {
  it.each([
    ["Woody", "woody"],
    ["wood", "woody"],
    ["Cedar", "woody"],
    ["sandalwood", "woody"],
    ["FRESH", "fresh"],
    ["clean", "fresh"],
    ["soapy", "fresh"],
    ["amber", "amber"],
    ["Oriental", "amber"],
    ["resin", "amber"],
    ["balsamic", "amber"],
    ["floral", "floral"],
    ["Rose", "floral"],
    ["white floral", "floral"],
    ["green", "green"],
    ["aromatic", "green"],
    ["herbal", "green"],
    ["citrus", "citrus"],
    ["spicy", "spicy"],
    ["warm spicy", "spicy"],
    ["musk", "musk"],
    ["musky", "musk"],
    ["powdery", "musk"],
    ["sweet", "gourmand"],
    ["vanilla", "gourmand"],
    ["gourmand", "gourmand"],
    ["fruity", "gourmand"],
    ["aquatic", "aquatic"],
    ["marine", "aquatic"],
    ["ozonic", "aquatic"],
  ] as const)("maps %s to %s", (label, key) => {
    expect(accordFromLabel(label)).toBe(key);
  });

  it("prefers the more distinctive family in a compound label", () => {
    expect(accordFromLabel("fresh spicy")).toBe("spicy");
  });

  it("matches whole words only", () => {
    expect(accordFromLabel("rosemary")).toBe("neutral");
  });

  it("returns neutral for unknown or empty input", () => {
    expect(accordFromLabel("nondescript")).toBe("neutral");
    expect(accordFromLabel("")).toBe("neutral");
    expect(accordFromLabel(null)).toBe("neutral");
    expect(accordFromLabel(undefined)).toBe("neutral");
  });
});

describe("accordFor", () => {
  it("uses the first top accord", () => {
    expect(accordFor({ top_accords: ["Citrus", "Woody"], olfactory_family: "Floral" })).toBe("citrus");
  });

  it("falls back to the olfactory family when the first accord is unknown", () => {
    expect(accordFor({ top_accords: ["mystery"], olfactory_family: "Amber" })).toBe("amber");
    expect(accordFor({ top_accords: [], olfactory_family: "Aquatic" })).toBe("aquatic");
  });

  it("falls back to neutral when nothing is recorded", () => {
    expect(accordFor({ top_accords: [], olfactory_family: null })).toBe("neutral");
    expect(accordFor({})).toBe("neutral");
  });
});

describe("accordVars", () => {
  it("points at the accord tokens", () => {
    expect(accordVars("woody")).toEqual({
      "--af": "var(--accord-woody-field)",
      "--ad": "var(--accord-woody-deep)",
      "--ac": "var(--chart-woody)",
    });
  });

  it("uses the musk chart color for neutral", () => {
    expect(accordVars("neutral")).toMatchObject({ "--ac": "var(--chart-musk)" });
  });
});
