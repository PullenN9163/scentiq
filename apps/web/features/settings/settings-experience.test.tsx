import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { SettingsExperience } from "./settings-experience";

it("keeps preference controls and API status available", () => {
  vi.spyOn(globalThis, "fetch").mockReturnValue(new Promise(() => undefined));
  render(<SettingsExperience />);
  expect(screen.getByLabelText(/maximum sprays/i)).toBeVisible();
    expect(
      screen.getByRole("heading", { name: /calendar connections/i }),
    ).toBeVisible();
  expect(screen.getByRole("status")).toHaveTextContent(/checking api/i);
});
