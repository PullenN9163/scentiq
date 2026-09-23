import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { WeekPlanner } from "./week-planner";

afterEach(cleanup);

describe("WeekPlanner", () => {
  it("renders all seven days and replaces a recommendation locally", async () => {
    const user = userEvent.setup();
    render(<WeekPlanner />);
    expect(screen.getAllByTestId("week-day")).toHaveLength(7);
    await user.click(screen.getAllByRole("button", { name: /replace recommendation/i })[0]);
    await user.click(screen.getByRole("button", { name: /choose linen & neroli/i }));
    expect(screen.getAllByText("Linen & Neroli").length).toBeGreaterThan(0);
    const firstDay = screen.getAllByTestId("week-day")[0];
    expect(within(firstDay).getByText(/3 sprays/i)).toBeVisible();
    expect(within(firstDay).getByText(/brighter direction/i)).toBeVisible();
  });

  it("validates the manual event form before adding an event", async () => {
    const user = userEvent.setup();
    render(<WeekPlanner />);
    await user.click(screen.getByRole("button", { name: /add manual event/i }));
    await user.click(screen.getByRole("button", { name: /add to week/i }));
    expect(await screen.findByText(/title is required/i)).toBeVisible();
    expect(screen.getByText(/time is required/i)).toBeVisible();
  });
});
