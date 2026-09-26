import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { discoveryResult } from "@/test/catalog-fixtures";

import { DiscoverExperience } from "./discover-experience";

vi.mock("@/lib/server/actions", () => ({ addToWishlist: vi.fn() }));

afterEach(cleanup);

describe("DiscoverExperience", () => {
  it("renders source-backed recommendations and supported filters", () => {
    render(<DiscoverExperience results={[discoveryResult()]} />);

    expect(screen.getByRole("heading", { name: "Source Scent" })).toBeVisible();
    expect(screen.getByText("Taste match")).toBeVisible();
    expect(screen.getByText("80%")).toBeVisible();
    expect(screen.getByLabelText("Family")).toBeVisible();
    expect(screen.getByRole("button", { name: /add to wishlist/i })).toBeVisible();
  });

  it("is honest when no recommendation is supported", () => {
    render(<DiscoverExperience results={[]} />);

    expect(screen.getByText("No recommendations yet")).toBeVisible();
    expect(screen.getByText(/will not invent a match/i)).toBeVisible();
  });
});
