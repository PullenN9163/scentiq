import { describe, expect, it } from "vitest";

import {
  getDemoCollection,
  getDemoFragranceById,
  getDemoLayeringSuggestions,
  getDemoToday,
  getDemoWeek,
} from "./index";

describe("ScentIQ demo domain", () => {
  it("resolves stable collection fragrance relationships", () => {
    const collection = getDemoCollection();
    expect(collection).toHaveLength(12);
    expect(collection.every((item) => getDemoFragranceById(item.fragranceId))).toBe(true);
  });

  it("provides seven recommendations that reference known fragrances", () => {
    const week = getDemoWeek();
    expect(week).toHaveLength(7);
    expect(
      week.every(
        (day) =>
          getDemoFragranceById(day.primary.fragranceId) &&
          day.alternatives.every((candidate) => getDemoFragranceById(candidate.fragranceId)),
      ),
    ).toBe(true);
  });

  it("keeps layering pairs within the shared fragrance catalog", () => {
    expect(
      getDemoLayeringSuggestions().every(
        (pair) => getDemoFragranceById(pair.fragranceAId) && getDemoFragranceById(pair.fragranceBId),
      ),
    ).toBe(true);
  });

  it("returns a coherent today view model", () => {
    const today = getDemoToday();
    expect(today.weather.date).toBe(today.recommendation.date);
    expect(today.events.every((event) => event.date === today.weather.date)).toBe(true);
  });
});
