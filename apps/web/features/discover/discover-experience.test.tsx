import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { DiscoverExperience } from "./discover-experience";

afterEach(cleanup);

describe("DiscoverExperience", () => {
  it("switches editorial discovery modes and filters by budget", async () => {
    const user = userEvent.setup();
    render(<DiscoverExperience />);
    await user.click(screen.getByRole("button", { name: "Challenge My Taste" }));
    expect(screen.getByText(/challenge mode/i)).toBeVisible();
    expect(screen.getByText("Night Orchard")).toBeVisible();
    await user.selectOptions(screen.getByLabelText(/redundancy tolerance/i), "High");
    await user.selectOptions(screen.getByLabelText(/budget/i), "100");
    expect(screen.getAllByTestId("discovery-card")).toHaveLength(1);
    await user.selectOptions(screen.getByLabelText(/fragrance family/i), "Leather");
    expect(screen.getByText(/no demo matches/i)).toBeVisible();
  });

  it("marks a candidate in the preview without claiming it was saved", async () => {
    const user = userEvent.setup();
    render(<DiscoverExperience />);
    await user.click(screen.getAllByRole("button", { name: /^mark in preview$/i })[0]);
    expect(screen.getAllByRole("button", { name: /marked in preview/i })[0]).toBeDisabled();
  });
});
