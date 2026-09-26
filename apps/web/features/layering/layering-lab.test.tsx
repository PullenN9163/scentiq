import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fragranceSummary, layeringSuggestion } from "@/test/catalog-fixtures";

import { LayeringLab } from "./layering-lab";

const getLayeringPair = vi.hoisted(() => vi.fn());
vi.mock("@/lib/server/actions", () => ({ getLayeringPair }));

afterEach(cleanup);
beforeEach(() => getLayeringPair.mockReset().mockResolvedValue(null));

const first = fragranceSummary();
const second = fragranceSummary({
  id: "22222222-2222-4222-8222-222222222222",
  name: "Second Source Scent",
});

describe("LayeringLab", () => {
  it("shows a scored pairing made only from owned fragrances", () => {
    render(
      <LayeringLab
        owned={[first, second]}
        suggestions={[layeringSuggestion()]}
        initialA={first.id}
      />,
    );

    expect(screen.getByLabelText("Fragrance A")).toHaveValue(first.id);
    expect(screen.getByRole("progressbar", { name: "Compatibility score" })).toBeVisible();
    expect(screen.getAllByText(/Source Scent \+ Second Source Scent/).length).toBeGreaterThan(0);
  });

  it("changes to a supported experimental suggestion", async () => {
    const user = userEvent.setup();
    const experimental = layeringSuggestion({ mode: "experimental", score: 0.62 });
    render(<LayeringLab owned={[first, second]} suggestions={[experimental]} />);

    await user.click(screen.getByRole("button", { name: "experimental" }));
    expect(screen.getByText("62% compatibility")).toBeVisible();
  });

  it("requires two owned fragrances", () => {
    render(<LayeringLab owned={[first]} suggestions={[]} />);
    expect(screen.getByText("Add at least two owned fragrances")).toBeVisible();
  });

  it("scores a selected pair that was not in the initial top results", async () => {
    const user = userEvent.setup();
    const third = fragranceSummary({
      id: "33333333-3333-4333-8333-333333333333",
      name: "Third Source Scent",
    });
    getLayeringPair.mockResolvedValue(
      layeringSuggestion({ first: second, second: third, score: 0.71 }),
    );
    render(<LayeringLab owned={[first, second, third]} suggestions={[layeringSuggestion()]} />);

    await user.selectOptions(screen.getByLabelText("Fragrance B"), third.id);
    await user.selectOptions(screen.getByLabelText("Fragrance A"), second.id);

    expect(await screen.findByRole("progressbar", { name: "Compatibility score" })).toHaveAttribute(
      "aria-valuenow",
      "71",
    );
    expect(getLayeringPair).toHaveBeenCalledWith(second.id, third.id, "safe");
  });
});
