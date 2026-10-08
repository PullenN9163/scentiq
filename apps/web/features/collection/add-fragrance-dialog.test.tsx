import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { fragranceSummary } from "@/test/catalog-fixtures";

import { AddFragranceDialog } from "./add-fragrance-dialog";

vi.mock("@/lib/server/actions", () => ({
  addToCollection: vi.fn(),
  createCustomFragrance: vi.fn(),
  searchCatalogPage: vi.fn().mockResolvedValue([]),
}));

describe("AddFragranceDialog", () => {
  it("lets a member select a catalog result from an informative result list", async () => {
    render(
      <AddFragranceDialog
        open
        onOpenChange={vi.fn()}
        catalog={[fragranceSummary({ concentration: "eau_de_parfum" })]}
        ownedFragranceIds={[]}
      />,
    );

    const result = screen.getByRole("radio", { name: /source scent/i });
    expect(result).toBeVisible();
    expect(screen.getAllByText("Source House").length).toBeGreaterThan(0);
    expect(screen.getByText("Eau de parfum")).toBeVisible();
    expect(screen.getByRole("button", { name: "Load more" })).toBeVisible();

    await userEvent.click(result);

    expect(screen.getByLabelText("Ownership")).toBeVisible();
    expect(screen.getByRole("button", { name: "Add to collection" })).toBeEnabled();
  });

  it("clears the selected fragrance as soon as the search changes", async () => {
    render(
      <AddFragranceDialog
        open
        onOpenChange={vi.fn()}
        catalog={[fragranceSummary()]}
        ownedFragranceIds={[]}
      />,
    );

    await userEvent.click(screen.getByRole("radio", { name: /source scent/i }));
    expect(screen.getByLabelText("Ownership")).toBeVisible();

    await userEvent.type(screen.getByRole("searchbox", { name: "Search the catalog" }), "new");

    expect(screen.queryByLabelText("Ownership")).not.toBeInTheDocument();
  });

  it("clears the selected fragrance when the dialog closes", async () => {
    const props = {
      onOpenChange: vi.fn(),
      catalog: [fragranceSummary()],
      ownedFragranceIds: [] as string[],
    };
    const { rerender } = render(<AddFragranceDialog open {...props} />);
    await userEvent.click(screen.getByRole("radio", { name: /source scent/i }));

    rerender(<AddFragranceDialog open={false} {...props} />);
    rerender(<AddFragranceDialog open {...props} />);

    expect(screen.queryByLabelText("Ownership")).not.toBeInTheDocument();
  });

  it("marks fragrances already in the collection as unavailable", () => {
    const owned = fragranceSummary();
    render(
      <AddFragranceDialog
        open
        onOpenChange={vi.fn()}
        catalog={[owned]}
        ownedFragranceIds={[owned.id]}
      />,
    );

    expect(screen.getByRole("radio", { name: /source scent/i })).toBeDisabled();
    expect(screen.getByText("Already in collection")).toBeVisible();
  });
});
