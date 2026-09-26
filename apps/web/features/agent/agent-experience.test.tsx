import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import {
  collectionInsights,
  fragranceDetail,
  layeringSuggestion,
} from "@/test/catalog-fixtures";

import { AgentExperience } from "./agent-experience";

afterEach(cleanup);

describe("AgentExperience", () => {
  it("answers supported quick actions with deterministic collection context", async () => {
    const user = userEvent.setup();
    render(
      <AgentExperience
        owned={[fragranceDetail()]}
        insights={collectionInsights()}
        layering={[layeringSuggestion()]}
      />,
    );
    await user.click(screen.getByRole("button", { name: "What should I wear today?" }));
    expect(screen.getByText(/Source Scent is the strongest catalog-supported match/i)).toBeVisible();
  });

  it("does not answer from fictional collection data", async () => {
    const user = userEvent.setup();
    render(
      <AgentExperience owned={[]} insights={collectionInsights({ total_items: 0 })} layering={[]} />,
    );
    await user.click(screen.getByRole("button", { name: "What should I wear today?" }));
    expect(screen.getByText(/owned collection is empty/i)).toBeVisible();
  });
});

describe("AgentExperience with today's context", () => {
  it("explains today's pick from the forecast and calendar", async () => {
    const user = userEvent.setup();
    render(
      <AgentExperience
        owned={[fragranceDetail()]}
        insights={collectionInsights()}
        layering={[]}
        today={{
          timeZone: "UTC",
          temperatureUnit: "celsius",
          day: {
            date: "2026-09-26",
            weather: {
              date: "2026-09-26",
              condition: "rain",
              high_celsius: 14,
              low_celsius: 9,
              precipitation_probability: 0.8,
              humidity: 85,
            },
            events: [
              {
                id: "e1",
                title: "Client pitch",
                starts_at: "2026-09-26T10:00:00Z",
                ends_at: "2026-09-26T11:00:00Z",
                is_all_day: false,
                location_label: null,
                occasion: "work",
                formality: "smart",
                is_hidden: false,
                calendar_name: "Work",
                provider: "microsoft",
              },
            ],
          },
        }}
      />,
    );

    expect(screen.getByRole("note")).toHaveTextContent(/forecast and connected calendars/);
    await user.click(screen.getByRole("button", { name: "What should I wear today?" }));
    expect(
      screen.getByText(/for today with 14°C and rain and your work plans \(Client pitch\)/),
    ).toBeVisible();
  });
});
