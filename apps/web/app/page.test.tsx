import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import Home from "./page";

it("presents the ScentIQ product loop and routes into the demo", () => {
  render(<Home />);

  expect(
    screen.getByRole("heading", { level: 1, name: "ScentIQ" }),
  ).toBeVisible();
  expect(screen.getByText(/your life already has a rhythm/i)).toBeVisible();
  expect(screen.getAllByRole("link", { name: /enter demo/i })).toHaveLength(2);
  expect(screen.getAllByRole("link", { name: /enter demo/i })[0]).toHaveAttribute("href", "/dashboard");
  expect(screen.getByText(/collection \+ schedule \+ weather/i)).toBeVisible();
});
