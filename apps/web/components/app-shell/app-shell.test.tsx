import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./app-shell";

vi.mock("next/navigation", () => ({ usePathname: () => "/collection" }));

// The shell reads the signed-in user from Clerk.
vi.mock("@clerk/nextjs", () => ({
  useUser: () => ({
    user: {
      fullName: "Maya Bennett",
      username: null,
      primaryEmailAddress: { emailAddress: "maya@example.test" },
    },
  }),
  UserButton: () => <button type="button">Account</button>,
}));

describe("AppShell", () => {
  it("marks the active destination and exposes mobile secondary navigation", async () => {
    const user = userEvent.setup();
    render(
      <AppShell>
        <p>Page content</p>
      </AppShell>,
    );

    expect(screen.getAllByRole("link", { name: /collection/i })[0]).toHaveAttribute(
      "aria-current",
      "page",
    );
    await user.click(screen.getByRole("button", { name: /more destinations/i }));
    const dialog = screen.getByRole("dialog", { name: /more destinations/i });
    expect(within(dialog).getByRole("link", { name: /layering lab/i })).toBeVisible();
    expect(screen.getByText("Page content")).toBeVisible();
    await user.click(within(dialog).getByRole("link", { name: /settings/i }));
    expect(screen.queryByRole("dialog", { name: /more destinations/i })).not.toBeInTheDocument();
  });

  it("shows the signed-in user rather than a demo identity", () => {
    render(
      <AppShell>
        <p>Page content</p>
      </AppShell>,
    );

    expect(screen.getByText("Maya Bennett")).toBeVisible();
    expect(screen.getByText("maya@example.test")).toBeVisible();
    expect(screen.queryByText(/demo mode/i)).not.toBeInTheDocument();
  });
});
