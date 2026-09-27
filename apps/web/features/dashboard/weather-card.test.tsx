import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WeatherCard } from "./weather-card";
import type { WeatherForecast } from "@/types/api";

function forecast(overrides: Partial<WeatherForecast> = {}): WeatherForecast {
  return {
    location_label: "Leeds, England, United Kingdom",
    timezone: "Europe/London",
    temperature_unit: "fahrenheit",
    fetched_at: "2026-09-26T15:00:00Z",
    stale: false,
    days: [
      {
        date: "2026-09-26",
        condition: "rain",
        high_celsius: 20,
        low_celsius: 10,
        precipitation_probability: 0.8,
        humidity: 75,
      },
    ],
    ...overrides,
  };
}

describe("WeatherCard", () => {
  it("shows today's forecast in the member's unit", () => {
    render(<WeatherCard weather={{ status: "ok", forecast: forecast() }} />);

    expect(screen.getByText("68°F")).toBeInTheDocument();
    expect(screen.getByText(/50°F/)).toBeInTheDocument();
    expect(screen.getByText("Rain · 80% chance of rain")).toBeInTheDocument();
    expect(screen.getByText("Leeds, England, United Kingdom")).toBeInTheDocument();
    expect(screen.queryByText(/unreachable/)).not.toBeInTheDocument();
  });

  it("uses Celsius when the member prefers it", () => {
    render(
      <WeatherCard
        weather={{ status: "ok", forecast: forecast({ temperature_unit: "celsius" }) }}
      />,
    );
    expect(screen.getByText("20°C")).toBeInTheDocument();
  });

  it("labels a stale forecast", () => {
    render(<WeatherCard weather={{ status: "ok", forecast: forecast({ stale: true }) }} />);
    expect(screen.getByRole("status")).toHaveTextContent(/unreachable/);
  });

  it("asks for a location when none is saved", () => {
    render(<WeatherCard weather={{ status: "location_required" }} />);
    expect(screen.getByText(/Add your location/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open settings" })).toHaveAttribute(
      "href",
      "/settings",
    );
  });

  it("explains an unresolved location", () => {
    render(<WeatherCard weather={{ status: "location_unresolved" }} />);
    expect(screen.getByText(/couldn't find your saved location/)).toBeInTheDocument();
  });

  it("degrades quietly when the provider is down", () => {
    render(<WeatherCard weather={{ status: "unavailable" }} />);
    expect(screen.getByRole("status")).toHaveTextContent(/unavailable right now/);
  });
});
