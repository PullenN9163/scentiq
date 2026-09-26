import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { fragranceDetail } from "@/test/catalog-fixtures";

import { WeekPlanner } from "./week-planner";

afterEach(cleanup);

const owned = [
  fragranceDetail(),
  fragranceDetail({
    id: "22222222-2222-4222-8222-222222222222",
    name: "Second Source Scent",
    rating_average: 3.8,
  }),
];

describe("WeekPlanner", () => {
  it("renders all seven days and cycles through owned fragrances", async () => {
    const user = userEvent.setup();
    render(<WeekPlanner owned={owned} />);

    expect(screen.getAllByTestId("week-day")).toHaveLength(7);
    await user.click(screen.getAllByRole("button", { name: /alternative/i })[0]);
    expect(screen.getAllByText("Second Source Scent").length).toBeGreaterThan(0);
  });

  it("does not fabricate a recommendation for an empty collection", () => {
    render(<WeekPlanner owned={[]} />);
    expect(screen.getByText("Your collection is empty")).toBeVisible();
  });
});
