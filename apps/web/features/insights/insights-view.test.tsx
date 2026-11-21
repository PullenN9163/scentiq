import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";

import { InsightsView } from "./insights-view";
import type { CollectionInsights } from "@/types/api";

// Recharts needs layout measurement that jsdom does not provide.
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  BarChart: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  Bar: () => null,
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
}));

function insights(
  overrides: Partial<CollectionInsights> = {},
): CollectionInsights {
  return {
    total_items: 2,
    owned_items: 2,
    wishlist_items: 0,
    retired_items: 0,
    custom_items: 0,
    total_purchase_value: "150.25",
    priced_items: 2,
    average_rating: 4.5,
    rated_items: 2,
    total_wears: 4,
    wears_last_30_days: 2,
    distinct_fragrances_worn: 2,
    most_worn: [
      {
        collection_item_id: "c1",
        fragrance_id: "f1",
        fragrance_name: "Source Scent",
        brand_name: "Source House",
        wear_count: 3,
      },
    ],
    accords: [{ label: "Woody", count: 2, share: 1 }],
    seasons: [{ label: "winter", count: 2, share: 1 }],
    occasions: [],
    ownership_types: [{ label: "bottle", count: 2 }],
    unclassified_items: 0,
    ...overrides,
  };
}

describe("InsightsView", () => {
  it("lets a member inspect the accord shares supplied by the API",async()=>{
    render(<InsightsView insights={insights({accords:[{label:"Woody",count:2,share:.667},{label:"Citrus",count:1,share:.333}]})}/>);
    await userEvent.click(screen.getByRole("button",{name:"Inspect Citrus accord"}));
    expect(screen.getByTestId("selected-profile")).toHaveTextContent("Citrus");
    expect(screen.getByTestId("selected-profile")).toHaveTextContent("33%");
    expect(screen.getByRole("button",{name:"Inspect Woody accord"})).toHaveTextContent("67%");
    expect(screen.getByText(/Share of the displayed recorded accord occurrences/)).toBeVisible();
  });
  it("renders the selected ring when an accord falls outside the first six", async () => {
    const {container} = render(<InsightsView insights={insights({accords:Array.from({length:8}, (_,index)=>({label:`Accord ${index+1}`,count:1,share:.125}))})}/>);
    await userEvent.click(screen.getByRole("button",{name:"Inspect Accord 8 accord"}));
    expect(screen.getByTestId("selected-profile")).toHaveTextContent("Accord 8");
    expect(container.querySelector('g[data-selected="true"]')).toHaveAttribute("data-accord","Accord 8");
  });
  it("keeps a valid selected ring when refreshed data has fewer accords", async () => {
    const accords = Array.from({length:8}, (_,index)=>({label:`Accord ${index+1}`,count:1,share:.125}));
    const {container,rerender} = render(<InsightsView insights={insights({accords})}/>);
    await userEvent.click(screen.getByRole("button",{name:"Inspect Accord 8 accord"}));
    rerender(<InsightsView insights={insights({accords:accords.slice(0,5).map(accord=>({...accord,share:.2}))})}/>);
    expect(container.querySelectorAll('g[data-accord]')).toHaveLength(5);
    expect(container.querySelector('g[data-selected="true"]')).toHaveAttribute("data-accord","Accord 5");
    expect(screen.getByRole("button",{name:"Inspect Accord 5 accord"})).toHaveAttribute("aria-pressed","true");
  });
  it("guides an empty account instead of rendering zeroes", () => {
    render(<InsightsView insights={insights({ total_items: 0 })} />);

    expect(screen.getByText("Nothing to analyse yet")).toBeVisible();
  });

  it("shows the money total as the decimal string the API returned", () => {
    render(<InsightsView insights={insights()} />);

    expect(screen.getByText("150.25")).toBeVisible();
  });

  it("says when nothing is priced rather than showing zero", () => {
    render(
      <InsightsView
        insights={insights({ total_purchase_value: null, priced_items: 0 })}
      />,
    );

    expect(screen.getByText("Not recorded")).toBeVisible();
  });

  it("reports how much of the collection the breakdowns cover", () => {
    render(
      <InsightsView
        insights={insights({
          total_items: 3,
          unclassified_items: 1,
          custom_items: 1,
        })}
      />,
    );

    expect(screen.getByText(/Based on 2 of 3 items/)).toBeVisible();
    expect(screen.getByText(/no classification data/)).toBeVisible();
  });

  it("explains an absent accord breakdown", () => {
    render(<InsightsView insights={insights({ accords: [] })} />);

    expect(
      screen.getByText(/None of your fragrances carry accord data/),
    ).toBeVisible();
  });

  it("notes when only some items have a price", () => {
    render(
      <InsightsView insights={insights({ priced_items: 1, total_items: 2 })} />,
    );

    expect(
      screen.getByText(/1 of 2 items have a recorded price/),
    ).toBeVisible();
  });

  it("ranks the most worn fragrance", () => {
    render(<InsightsView insights={insights()} />);

    expect(screen.getByText("Source Scent")).toBeVisible();
    expect(screen.getByText("3")).toBeVisible();
  });

  it("shows neglected value and seasonal evidence without inventing occasion coverage", () => {
    render(
      <InsightsView
        insights={insights({
          neglected: [
            {
              collection_item_id: "n1",
              fragrance_id: "n",
              fragrance_name: "Quiet bottle",
              brand_name: "House",
              wear_count: 0,
              last_worn_at: null,
              user_rating: null,
              cost_per_wear: null,
            },
          ],
          cost_per_wear: [
            {
              collection_item_id: "v1",
              fragrance_id: "v",
              fragrance_name: "Good value",
              brand_name: "House",
              wear_count: 4,
              last_worn_at: "2026-10-07T00:00:00Z",
              user_rating: 5,
              cost_per_wear: "25.00",
            },
          ],
          season_coverage_score: 0.4,
          season_evidence_coverage: 0.5,
          season_gaps: ["summer"],
          occasion_behavior: [],
        })}
      />,
    );
    expect(screen.getByText("Quiet bottle")).toBeVisible();
    expect(screen.getByText(/25.00 per wear/)).toBeVisible();
    expect(
      screen.getByText(/50% of owned fragrances have season evidence/),
    ).toBeVisible();
    expect(screen.getByText(/Not enough occasion history yet/)).toBeVisible();
  });
});
