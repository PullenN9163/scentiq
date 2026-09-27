import type {
  ForecastDay,
  TemperatureUnit,
  WeatherCondition,
  WeatherForecast,
} from "@/types/api";

/** The forecast, or the reason a screen has none to show. */
export type WeatherResult =
  | { status: "ok"; forecast: WeatherForecast }
  | { status: "location_required" }
  | { status: "location_unresolved" }
  | { status: "unavailable" };

/** Forecasts arrive in Celsius; members choose how they are shown. */

export const DEFAULT_TEMPERATURE_UNIT: TemperatureUnit = "fahrenheit";

export function toUnit(celsius: number, unit: TemperatureUnit): number {
  return Math.round(unit === "celsius" ? celsius : (celsius * 9) / 5 + 32);
}

export function formatTemperature(celsius: number, unit: TemperatureUnit): string {
  return `${toUnit(celsius, unit)}°${unit === "celsius" ? "C" : "F"}`;
}

const CONDITION_LABELS: Record<WeatherCondition, string> = {
  clear: "Clear",
  partly_cloudy: "Partly cloudy",
  cloudy: "Cloudy",
  fog: "Fog",
  drizzle: "Drizzle",
  rain: "Rain",
  snow: "Snow",
  thunderstorm: "Thunderstorms",
  unknown: "Mixed conditions",
};

export function conditionLabel(condition: WeatherCondition): string {
  return CONDITION_LABELS[condition];
}

/** Below 20 °C (68 °F) counts as cool for fragrance planning. */
export const COOL_HIGH_CELSIUS = 20;

export function isCool(day: ForecastDay): boolean {
  return day.high_celsius < COOL_HIGH_CELSIUS;
}

export function formatPrecipitation(probability: number | null): string | null {
  if (probability === null) return null;
  return `${Math.round(probability * 100)}% chance of rain`;
}
