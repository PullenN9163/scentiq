import { render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import Home from "./page";

afterEach(() => {
  vi.restoreAllMocks();
});

it("renders the ScentIQ foundation shell with an accessible API status", () => {
  vi.spyOn(globalThis, "fetch").mockReturnValue(new Promise(() => undefined));

  render(<Home />);

  expect(
    screen.getByRole("heading", { level: 1, name: "ScentIQ" }),
  ).toBeVisible();
  expect(screen.getByText(/foundation stage/i)).toBeVisible();
  expect(screen.getByRole("status")).toHaveAttribute("aria-live", "polite");
});
