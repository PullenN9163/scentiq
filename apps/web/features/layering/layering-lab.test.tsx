import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { fragranceSummary, layeringSuggestion } from "@/test/catalog-fixtures";

import { LayeringLab } from "./layering-lab";

afterEach(cleanup);

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
});
