import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { TodayDashboard } from "./today-dashboard";

afterEach(cleanup);

describe("TodayDashboard", () => {
  it("cycles alternatives and keeps detail actions linked to the selected fragrance", async () => {
    const user = userEvent.setup();
    render(<TodayDashboard />);

    expect(screen.getByRole("heading", { name: "Cedar After Rain" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: /another option/i }));
    expect(screen.getByRole("heading", { name: "Linen & Neroli" })).toBeVisible();
    expect(screen.getByRole("link", { name: /view details/i })).toHaveAttribute("href", "/collection/linen-neroli");
  });

  it("dismisses the current recommendation for the session", async () => {
    const user = userEvent.setup();
    render(<TodayDashboard />);
    await user.click(screen.getByRole("button", { name: /dismiss/i }));
    expect(screen.getByText(/recommendation dismissed/i)).toBeVisible();
  });
});
