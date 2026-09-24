import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CollectionView } from "./collection-view";
import type { CollectionItem, FragranceSummary } from "@/types/api";

// The dialog submits through Server Actions, which do not exist in jsdom.
vi.mock("@/lib/server/actions", () => ({
  addToCollection: vi.fn(),
  createCustomFragrance: vi.fn(),
  updateCollectionItem: vi.fn(),
  logWear: vi.fn(),
}));

function fragrance(overrides: Partial<FragranceSummary> = {}): FragranceSummary {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    name: "Cedar After Rain",
    concentration: "eau_de_parfum",
    release_year: 2026,
    image_blob_path: null,
    longevity_score: 7,
    projection_level: "moderate",
    brand: { id: "b1", name: "Atelier North", slug: "atelier-north" },
    is_custom: false,
    ...overrides,
  };
}

function item(overrides: Partial<CollectionItem> = {}): CollectionItem {
  return {
    id: "22222222-2222-4222-8222-222222222222",
    ownership_type: "bottle",
    bottle_size_ml: 100,
    remaining_ml: 62,
    purchase_price: "145.00",
    purchase_date: "2026-01-12",
    user_rating: 4,
    custom_longevity: null,
    custom_projection: null,
    status: "owned",
    fragrance: fragrance(),
    ...overrides,
  };
}

describe("CollectionView", () => {
  it("shows onboarding guidance for an empty account", () => {
    render(<CollectionView items={[]} catalog={[]} />);

    expect(screen.getByText("Start your fragrance wardrobe")).toBeVisible();
    // Filters are pointless with nothing to filter.
    expect(screen.queryByLabelText("Search collection")).not.toBeInTheDocument();
  });

  it("renders persisted collection items", () => {
    render(<CollectionView items={[item()]} catalog={[]} />);

    expect(screen.getByRole("heading", { name: "Cedar After Rain" })).toBeVisible();
    expect(screen.getByText("62ml of 100ml remaining")).toBeVisible();
    expect(screen.getByText("★ 4")).toBeVisible();
  });

  it("says so rather than showing a zero when nothing is recorded", () => {
    render(
      <CollectionView items={[item({ user_rating: null, remaining_ml: null })]} catalog={[]} />,
    );

    expect(screen.getByText("Not rated")).toBeVisible();
    expect(screen.getByText("No volume recorded")).toBeVisible();
  });

  it("marks a custom entry", () => {
    render(
      <CollectionView
        items={[item({ fragrance: fragrance({ is_custom: true }) })]}
        catalog={[]}
      />,
    );

    expect(screen.getByText("Custom")).toBeVisible();
  });

  it("filters by search term", async () => {
    const other = item({
      id: "33333333-3333-4333-8333-333333333333",
      fragrance: fragrance({ id: "44444444-4444-4444-8444-444444444444", name: "Fig Circuit" }),
    });
    render(<CollectionView items={[item(), other]} catalog={[]} />);

    await userEvent.type(screen.getByLabelText("Search collection"), "fig");

    expect(screen.getByRole("heading", { name: "Fig Circuit" })).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Cedar After Rain" })).not.toBeInTheDocument();
  });

  it("offers a way back when a filter matches nothing", async () => {
    render(<CollectionView items={[item()]} catalog={[]} />);

    await userEvent.type(screen.getByLabelText("Search collection"), "nothing matches");

    expect(screen.getByText("No fragrances found")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(screen.getByRole("heading", { name: "Cedar After Rain" })).toBeVisible();
  });

  it("shows retired status on the card", () => {
    render(<CollectionView items={[item({ status: "finished" })]} catalog={[]} />);

    // Scoped to the card: "Finished" is also a filter option.
    const card = screen.getByTestId("fragrance-card");
    expect(within(card).getByText("Finished")).toBeVisible();
  });
});
