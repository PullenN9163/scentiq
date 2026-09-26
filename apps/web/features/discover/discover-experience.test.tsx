import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { discoveryResult, fragranceSummary } from "@/test/catalog-fixtures";

import { DiscoverExperience } from "./discover-experience";

vi.mock("@/lib/server/actions", () => ({
  addToWishlist: vi.fn(),
  searchCatalogPage: vi.fn().mockResolvedValue([]),
}));

afterEach(cleanup);

describe("DiscoverExperience", () => {
  it("renders source-backed recommendations and supported filters", () => {
    render(<DiscoverExperience results={[discoveryResult()]} />);

    expect(screen.getByRole("heading", { name: "Source Scent" })).toBeVisible();
    expect(screen.getByText("Taste match")).toBeVisible();
    expect(screen.getByText("80%")).toBeVisible();
    expect(screen.getByLabelText("Family")).toBeVisible();
    expect(screen.getByRole("button", { name: /add to wishlist/i })).toBeVisible();
    expect(screen.getByRole("link", { name: "View details" })).toHaveAttribute(
      "href",
      "/collection/11111111-1111-4111-8111-111111111111?from=discover",
    );
  });

  it("is honest when no recommendation is supported", () => {
    render(<DiscoverExperience results={[]} />);

    expect(screen.getByText("No recommendations yet")).toBeVisible();
    expect(screen.getByText(/will not invent a match/i)).toBeVisible();
  });

  it("shows direct catalog matches instead of recommendation scores during search", () => {
    render(
      <DiscoverExperience
        results={[discoveryResult()]}
        query="source"
        catalogResults={[fragranceSummary({ concentration: "eau_de_parfum" })]}
      />,
    );

    expect(screen.getByRole("searchbox", { name: "Search the fragrance catalog" })).toHaveValue(
      "source",
    );
    expect(screen.getByRole("heading", { name: "Source Scent" })).toBeVisible();
    expect(screen.getByText("Eau de parfum")).toBeVisible();
    expect(screen.queryByText("Taste match")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View details" })).toHaveAttribute(
      "href",
      "/collection/11111111-1111-4111-8111-111111111111?from=discover&q=source",
    );
  });

  it("explains when catalog search has no matches", () => {
    render(<DiscoverExperience results={[]} query="missing" catalogResults={[]} />);

    expect(screen.getByText('No fragrances found for “missing”')).toBeVisible();
    expect(screen.getByRole("link", { name: "Clear search" })).toHaveAttribute(
      "href",
      "/discover",
    );
  });
});
