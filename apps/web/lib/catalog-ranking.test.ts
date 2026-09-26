import { describe, expect, it } from "vitest";

import { fragranceDetail } from "@/test/catalog-fixtures";

import { rankFragrances, seasonForMonth } from "./catalog-ranking";

describe("catalog ranking", () => {
  it("maps calendar months to fragrance seasons", () => {
    expect([0, 3, 6, 9].map(seasonForMonth)).toEqual(["winter", "spring", "summer", "fall"]);
  });

  it("prefers recorded season and daypart signals", () => {
    const nightFall = fragranceDetail({
      id: "22222222-2222-4222-8222-222222222222",
      seasons: [{ season: "fall", weight: 1 }],
      community: {
        ...fragranceDetail().community!,
        day_votes: 1,
        night_votes: 9,
      },
    });
    const daySpring = fragranceDetail({
      seasons: [{ season: "spring", weight: 1 }],
      community: {
        ...fragranceDetail().community!,
        day_votes: 9,
        night_votes: 1,
      },
    });

    expect(
      rankFragrances([daySpring, nightFall], {
        season: "fall",
        daypart: "night",
        coolWeather: true,
      })[0].id,
    ).toBe(nightFall.id);
  });
});
