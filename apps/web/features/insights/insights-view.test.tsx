import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { InsightsView } from "./insights-view";
import type { CollectionInsights } from "@/types/api";

// Recharts needs layout measurement that jsdom does not provide.
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => null,
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
}));

function insights(overrides: Partial<CollectionInsights> = {}): CollectionInsights {
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
        fragrance_name: "Cedar After Rain",
        brand_name: "Atelier North",
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
  it("guides an empty account instead of rendering zeroes", () => {
    render(<InsightsView insights={insights({ total_items: 0 })} />);

    expect(screen.getByText("Nothing to analyse yet")).toBeVisible();
  });

  it("shows the money total as the decimal string the API returned", () => {
    render(<InsightsView insights={insights()} />);

    expect(screen.getByText("150.25")).toBeVisible();
  });

  it("says when nothing is priced rather than showing zero", () => {
    render(<InsightsView insights={insights({ total_purchase_value: null, priced_items: 0 })} />);

    expect(screen.getByText("Not recorded")).toBeVisible();
  });

  it("reports how much of the collection the breakdowns cover", () => {
    render(
      <InsightsView
        insights={insights({ total_items: 3, unclassified_items: 1, custom_items: 1 })}
      />,
    );

    expect(screen.getByText(/Based on 2 of 3 items/)).toBeVisible();
    expect(screen.getByText(/no classification data/)).toBeVisible();
  });

  it("explains an absent accord breakdown", () => {
    render(<InsightsView insights={insights({ accords: [] })} />);

    expect(screen.getByText(/None of your fragrances carry accord data/)).toBeVisible();
  });

  it("notes when only some items have a price", () => {
    render(<InsightsView insights={insights({ priced_items: 1, total_items: 2 })} />);

    expect(screen.getByText(/1 of 2 items have a recorded price/)).toBeVisible();
  });

  it("ranks the most worn fragrance", () => {
    render(<InsightsView insights={insights()} />);

    expect(screen.getByText("Cedar After Rain")).toBeVisible();
    expect(screen.getByText("3")).toBeVisible();
  });
});
