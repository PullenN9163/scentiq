import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { discoveryResult, fragranceSummary } from "@/test/catalog-fixtures";

import { DiscoverExperience } from "./discover-experience";
import { searchCatalogPage } from "@/lib/server/actions";

vi.mock("@/lib/server/actions", () => ({
  addToWishlist: vi.fn(),
  searchCatalogPage: vi.fn().mockResolvedValue([]),
}));

afterEach(cleanup);

describe("DiscoverExperience", () => {
  it("reflects all active filters", () => {
    render(<DiscoverExperience results={[]} selectedFamily="Woody" selectedGender="unisex" selectedMinimumValue="4" />);
    expect(screen.getByLabelText("Family")).toHaveValue("Woody");
    expect(screen.getByLabelText("Gender")).toHaveValue("unisex");
    expect(screen.getByLabelText("Minimum value rating")).toHaveValue("4");
  });
  it("replaces catalog results when the search changes", () => {
    const { rerender } = render(<DiscoverExperience results={[]} query="first" catalogResults={[fragranceSummary({name:"First scent"})]} />);
    rerender(<DiscoverExperience results={[]} query="second" catalogResults={[fragranceSummary({name:"Second scent"})]} />);
    expect(screen.getByRole("heading", {name:"Second scent"})).toBeVisible();
    expect(screen.queryByRole("heading", {name:"First scent"})).not.toBeInTheDocument();
    expect(screen.getByRole("searchbox")).toHaveValue("second");
  });
  it("keeps search available when recommendations fail", () => {
    render(<DiscoverExperience results={[]} recommendationError="Recommendations are unavailable. Try again." />);
    expect(screen.getByRole("searchbox")).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent("Recommendations are unavailable");
    expect(screen.queryByText("No recommendations yet")).not.toBeInTheDocument();
  });
  it("preserves matches and allows retry after pagination fails", async () => {
    vi.mocked(searchCatalogPage).mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce([]);
    const items = Array.from({length:25}, (_, index) => fragranceSummary({id:`item-${index}`,name:`Scent ${index}`}));
    render(<DiscoverExperience results={[]} query="scent" catalogResults={items} />);
    const loadMore = screen.getByText("Load more", {selector:"button"});
    fireEvent.click(loadMore);
    expect(await screen.findByText(/Could not load more/)).toBeVisible();
    expect(screen.getAllByTestId("catalog-result-card")).toHaveLength(25);
    await waitFor(()=>expect(loadMore).toBeEnabled());
    fireEvent.click(loadMore);
    await waitFor(()=>expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  },10000);
  it("shows the selected discovery direction, season and supporting reasons", () => {
    render(
      <DiscoverExperience
        mode="explore"
        selectedSeason="summer"
        results={[
          discoveryResult({
            reasons: ["A new amber profile"],
            evidence_coverage: 0.5,
          }),
        ]}
      />,
    );
    expect(screen.getByLabelText("Discovery direction")).toHaveValue("explore");
    expect(screen.getByLabelText("Season")).toHaveValue("summer");
    expect(screen.getByText("A new amber profile")).toBeVisible();
    expect(screen.getByText(/50% catalog evidence/)).toBeVisible();
  });
  it("shows an existing wishlist entry as saved and prevents another add", () => {
    render(
      <DiscoverExperience
        results={[discoveryResult()]}
        wishlistIds={["11111111-1111-4111-8111-111111111111"]}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Saved to wishlist" }),
    ).toBeDisabled();
    expect(
      screen.queryByRole("button", { name: "Add to wishlist" }),
    ).not.toBeInTheDocument();
  });
  it("renders source-backed recommendations and supported filters", () => {
    render(<DiscoverExperience results={[discoveryResult()]} />);

    expect(screen.getByRole("heading", { name: "Source Scent" })).toBeVisible();
    expect(screen.getByText("Taste match")).toBeVisible();
    expect(screen.getByText("80%")).toBeVisible();
    expect(screen.getByLabelText("Family")).toBeVisible();
    expect(
      screen.getByRole("button", { name: /add to wishlist/i }),
    ).toBeVisible();
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

    expect(
      screen.getByRole("searchbox", { name: "Search the fragrance catalog" }),
    ).toHaveValue("source");
    expect(screen.getByRole("heading", { name: "Source Scent" })).toBeVisible();
    expect(screen.getByText("Eau de parfum")).toBeVisible();
    expect(screen.queryByText("Taste match")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View details" })).toHaveAttribute(
      "href",
      "/collection/11111111-1111-4111-8111-111111111111?from=discover&q=source",
    );
  });

  it("explains when catalog search has no matches", () => {
    render(
      <DiscoverExperience results={[]} query="missing" catalogResults={[]} />,
    );

    expect(screen.getByText("No fragrances found for “missing”")).toBeVisible();
    expect(screen.getByRole("link", { name: "Clear search" })).toHaveAttribute(
      "href",
      "/discover",
    );
  });
});
