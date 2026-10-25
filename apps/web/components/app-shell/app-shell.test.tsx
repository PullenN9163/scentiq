import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./app-shell";

vi.mock("next/navigation", () => ({ usePathname: () => "/collection", useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/server/collection-search", () => ({ searchOwnCollection: vi.fn().mockResolvedValue([]) }));

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
  it("shares every destination across desktop tablet and phone navigation", async () => {
    const user = userEvent.setup();
    render(
      <AppShell>
        <p>Page content</p>
      </AppShell>,
    );

    const destinations = ["Today", "My Week", "Collection", "Layering Lab", "Discover", "Insights", "Agent", "Settings"];
    const desktop = screen.getByRole("navigation", { name: "Primary navigation" });
    const tablet = screen.getByRole("navigation", { name: "Tablet navigation" });
    const phone = screen.getByRole("navigation", { name: "Mobile navigation" });

    for (const destination of destinations) {
      expect(within(desktop).getByRole("link", { name: destination })).toBeVisible();
      expect(within(tablet).getByRole("link", { name: destination })).toBeVisible();
    }

    expect(within(phone).getByRole("link", { name: "Collection" })).toHaveAttribute("aria-current", "page");
    expect(within(tablet).getByRole("link", { name: "Collection" })).toHaveAttribute("aria-current", "page");
    expect(within(desktop).getByRole("link", { name: "Collection" })).toHaveAttribute("aria-current", "page");

    await user.click(within(phone).getByRole("button", { name: "More destinations" }));
    const phonePanel = screen.getByRole("dialog", { name: "More destinations" });
    for (const destination of ["Layering Lab", "Insights", "Agent", "Settings"]) {
      expect(within(phonePanel).getByRole("link", { name: destination })).toBeVisible();
    }
  });

  it("opens and closes the tablet destination panel accessibly", async () => {
    const user = userEvent.setup();
    render(
      <AppShell>
        <p>Page content</p>
      </AppShell>,
    );

    const tablet = screen.getByRole("navigation", { name: "Tablet navigation" });
    const menu = within(tablet).getByRole("button", { name: "Open navigation menu" });
    expect(menu).toHaveAttribute("aria-expanded", "false");

    await user.click(menu);
    expect(menu).toHaveAttribute("aria-expanded", "true");
    const panel = screen.getByRole("navigation", { name: "Tablet destinations" });
    await user.click(within(panel).getByRole("link", { name: "Settings" }));
    expect(screen.queryByRole("navigation", { name: "Tablet destinations" })).not.toBeInTheDocument();
    expect(menu).toHaveAttribute("aria-expanded", "false");
  });

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
