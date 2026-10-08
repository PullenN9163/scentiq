import { describe, expect, it } from "vitest";

import {
  conditionLabel,
  formatPrecipitation,
  formatTemperature,
  isCool,
  toUnit,
} from "@/lib/weather";

describe("weather formatting", () => {
  it("converts Celsius for display", () => {
    expect(toUnit(20, "fahrenheit")).toBe(68);
    expect(toUnit(18.6, "celsius")).toBe(19);
    expect(formatTemperature(0, "fahrenheit")).toBe("32°F");
    expect(formatTemperature(-3.4, "celsius")).toBe("-3°C");
  });

  it("labels conditions and rain chances", () => {
    expect(conditionLabel("partly_cloudy")).toBe("Partly cloudy");
    expect(formatPrecipitation(0.42)).toBe("42% chance of rain");
    expect(formatPrecipitation(null)).toBeNull();
  });

  it("treats a high below 20 °C as cool", () => {
    const day = {
      date: "2026-09-26",
      condition: "clear" as const,
      low_celsius: null,
      precipitation_probability: null,
      humidity: null,
    };
    expect(isCool({ ...day, high_celsius: 19.9 })).toBe(true);
    expect(isCool({ ...day, high_celsius: 20 })).toBe(false);
  });
});
