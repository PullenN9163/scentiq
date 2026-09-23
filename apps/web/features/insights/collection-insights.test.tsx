import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CollectionInsights } from "./collection-insights";

describe("CollectionInsights", () => {
  it("renders key metrics, chart summaries, and coverage classifications", () => {
    render(<CollectionInsights />);
    expect(screen.getByText("12")).toBeVisible();
    expect(screen.getByRole("img", { name: /accord distribution/i })).toBeVisible();
    expect(screen.getAllByText(/good|excellent|moderate|weak/i).length).toBeGreaterThan(4);
    expect(screen.getByText(/underrepresented/i)).toBeVisible();
  });
});
