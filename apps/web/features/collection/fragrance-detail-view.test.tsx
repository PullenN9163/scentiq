import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { fragranceDetail } from "@/test/catalog-fixtures";

import { FragranceDetailView } from "./fragrance-detail-view";

vi.mock("@/lib/server/actions", () => ({
  logWear: vi.fn(),
  updateCollectionItem: vi.fn(),
}));

describe("FragranceDetailView", () => {
  it("returns a Discover visitor to their catalog search", () => {
    render(
      <FragranceDetailView
        fragrance={fragranceDetail()}
        ownedItem={null}
        wears={[]}
        backHref="/discover?q=source"
        backLabel="Back to Discover"
      />,
    );

    expect(screen.getByRole("link", { name: /Back to Discover/ })).toHaveAttribute(
      "href",
      "/discover?q=source",
    );
  });
});
