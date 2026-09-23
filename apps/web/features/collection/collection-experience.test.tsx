import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { CollectionExperience } from "./collection-experience";
import { FragranceDetail } from "./fragrance-detail";

afterEach(cleanup);

describe("CollectionExperience", () => {
  it("searches the collection and keeps result links routed by stable ID", async () => {
    const user = userEvent.setup();
    render(<CollectionExperience />);
    await user.type(screen.getByRole("searchbox", { name: /search collection/i }), "cedar after");
    expect(screen.getAllByTestId("fragrance-card")).toHaveLength(1);
    expect(screen.getByRole("link", { name: /open cedar after rain/i })).toHaveAttribute("href", "/collection/cedar-after-rain");
  });

  it("validates the add-fragrance form", async () => {
    const user = userEvent.setup();
    render(<CollectionExperience />);
    await user.click(screen.getByRole("button", { name: /add fragrance/i }));
    await user.click(screen.getByRole("button", { name: /add to collection/i }));
    expect(await screen.findByText(/choose a fragrance/i, { selector: ".field-error" })).toBeVisible();
  });

  it("supports a frontend-only edit interaction on detail", async () => {
    const user = userEvent.setup();
    render(<FragranceDetail fragranceId="cedar-after-rain" />);
    await user.click(screen.getByRole("button", { name: /^edit$/i }));
    expect(screen.getByRole("dialog", { name: /edit cedar after rain/i })).toBeVisible();
  });
});
