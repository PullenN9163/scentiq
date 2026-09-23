import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, describe, expect, it } from "vitest";

import { AppShell } from "./app-shell";

vi.mock("next/navigation", () => ({ usePathname: () => "/collection" }));

describe("AppShell", () => {
  it("marks the active destination and exposes mobile secondary navigation", async () => {
    const user = userEvent.setup();
    render(<AppShell><p>Page content</p></AppShell>);

    expect(screen.getAllByRole("link", { name: /collection/i })[0]).toHaveAttribute("aria-current", "page");
    await user.click(screen.getByRole("button", { name: /more destinations/i }));
    expect(within(screen.getByRole("dialog", { name: /more destinations/i })).getByRole("link", { name: /layering lab/i })).toBeVisible();
    expect(screen.getByText("Page content")).toBeVisible();
  });
});
