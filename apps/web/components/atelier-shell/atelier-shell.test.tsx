import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ThemeProvider } from "@/components/ui/theme-provider";

import { AtelierShell, CATALOG_ATTRIBUTION } from "./atelier-shell";
import { activeDestination } from "./navigation";

const navigation = vi.hoisted(() => ({ pathname: "/collection/abc" }));
const clerk = vi.hoisted(() => ({ signOut: vi.fn(), openUserProfile: vi.fn() }));

vi.mock("next/navigation", () => ({ usePathname: () => navigation.pathname, useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/server/collection-search", () => ({ searchOwnCollection: vi.fn().mockResolvedValue([]) }));
vi.mock("@clerk/nextjs", () => ({
  useUser: () => ({ user: { fullName: "Maya Bennett", username: null, primaryEmailAddress: { emailAddress: "maya@example.test" } } }),
  useClerk: () => clerk,
  UserButton: () => <button type="button">Account</button>,
}));

function renderShell() {
  return render(
    <ThemeProvider>
      <AtelierShell>
        <p>Page content</p>
      </AtelierShell>
    </ThemeProvider>,
  );
}

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
  navigation.pathname = "/collection/abc";
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: false, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
});
afterEach(() => vi.unstubAllGlobals());

describe("AtelierShell", () => {
  it("offers the five destinations in order in the top bar and the dock", () => {
    renderShell();
    const names = ["Today", "Week", "Blend", "Collection", "Discover"];
    for (const label of ["Primary navigation", "Dock navigation"]) {
      const nav = screen.getByRole("navigation", { name: label });
      expect(within(nav).getAllByRole("link").map((link) => link.textContent)).toEqual(names);
    }
    expect(screen.queryByRole("link", { name: "Insights" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Agent" })).not.toBeInTheDocument();
  });

  it("marks the active destination, including fragrance pages under Collection", () => {
    renderShell();
    for (const label of ["Primary navigation", "Dock navigation"]) {
      const nav = screen.getByRole("navigation", { name: label });
      expect(within(nav).getByRole("link", { name: "Collection" })).toHaveAttribute("aria-current", "page");
      expect(within(nav).getByRole("link", { name: "Today" })).not.toHaveAttribute("aria-current");
    }
  });

  it("keeps the skip link, the main landmark and the catalogue attribution", () => {
    renderShell();
    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute("href", "#main-content");
    const main = screen.getByRole("main");
    expect(main).toHaveAttribute("id", "main-content");
    expect(main).toHaveAttribute("tabindex", "-1");
    expect(main).toHaveTextContent(CATALOG_ATTRIBUTION);
  });

  it("opens the command menu from Ask", async () => {
    const listener = vi.fn();
    window.addEventListener("scentiq:command", listener);
    renderShell();
    await userEvent.click(screen.getAllByRole("button", { name: /Ask/ })[0]);
    expect(listener).toHaveBeenCalled();
    window.removeEventListener("scentiq:command", listener);
  });

  it("puts Your taste, Settings, appearance and sign out in the account menu", async () => {
    renderShell();
    await userEvent.click(screen.getAllByRole("button", { name: "Account menu" })[0]);
    const menu = await screen.findByRole("menu");
    expect(within(menu).getByRole("menuitem", { name: "Your taste" })).toHaveAttribute("href", "/insights");
    expect(within(menu).getByRole("menuitem", { name: "Settings" })).toHaveAttribute("href", "/settings");
    expect(within(menu).getByRole("menuitemradio", { name: "Dark" })).toBeInTheDocument();
    await userEvent.click(within(menu).getByRole("menuitem", { name: "Sign out" }));
    expect(clerk.signOut).toHaveBeenCalledWith({ redirectUrl: "/" });
  });
});

describe("activeDestination", () => {
  it.each([
    ["/dashboard", "today"],
    ["/week", "week"],
    ["/layering", "blend"],
    ["/collection", "collection"],
    ["/collection/123", "collection"],
    ["/discover", "discover"],
    ["/insights", null],
    ["/settings", null],
    ["/weekly", null],
  ])("maps %s to %s", (path, value) => {
    expect(activeDestination(path)).toBe(value);
  });
});
