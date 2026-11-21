import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { discoveryResult, fragranceSummary } from "@/test/catalog-fixtures";

import { DiscoverAtelier } from "./discover-atelier";
import { discoverHref, reasonFor, suitsWords } from "./discover-copy";

const router = vi.hoisted(() => ({ push: vi.fn(), refresh: vi.fn(), replace: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));
const server = vi.hoisted(() => ({ addToWishlist: vi.fn(), addToCollection: vi.fn(), searchCatalogPage: vi.fn() }));
vi.mock("@/lib/server/actions", () => server);

const results = ["Hero Scent", "Second", "Third"].map((name, index) => discoveryResult({ fragrance: fragranceSummary({ id: `00000000-0000-4000-8000-00000000000${index}`, name }), reasons: index === 0 ? ["Adds a fresh dimension to your woody shelf"] : [] }));
const fetchMock = vi.fn();

beforeEach(() => {
  server.addToWishlist.mockResolvedValue(undefined);
  server.addToCollection.mockResolvedValue({ status: "success" });
  fetchMock.mockImplementation(async (url: string) => {
    if (url.startsWith("/api/discover/wishlist")) return new Response(JSON.stringify([]), { status: 200 });
    if (url.startsWith("/api/discover/feed")) return new Response(JSON.stringify({ items: results, refresh_status: "fresh" }), { status: 200 });
    if (url.startsWith("/api/discover/search")) return new Response(JSON.stringify([fragranceSummary({ id: "00000000-0000-4000-8000-0000000000aa", name: "Found" })]), { status: 200 });
    return new Response("{}", { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: false, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  window.history.replaceState({}, "", "/discover");
});
afterEach(() => { vi.clearAllMocks(); vi.unstubAllGlobals(); });

describe("discover copy", () => {
  it("uses the first reason or builds one in words", () => {
    expect(reasonFor({ reasons: ["Adds something fresh"], taste_match: 0, collection_expansion: 0 })).toBe("Adds something fresh.");
    expect(reasonFor({ reasons: [], taste_match: 0.8, collection_expansion: 0.7 })).toBe("Close to what you love, and it adds something new to your shelf.");
    expect(reasonFor({ taste_match: 0.2, collection_expansion: 0.1 })).toBe("A step away from your usual taste, and it sits close to what you already own.");
    expect(reasonFor({ taste_match: 0.5, collection_expansion: 0.4 })).not.toMatch(/\d/);
    expect(suitsWords({ taste_match: 0.8, collection_expansion: 0.6 })).toEqual(["Fits your taste", "Adds something new"]);
  });

  it("keeps the existing URL parameters", () => {
    expect(discoverHref("cedar", { mode: "seasonal", family: "Woody", season: "fall", gender: "unisex", minimum_value: "4" })).toBe("/discover?q=cedar&mode=seasonal&family=Woody&season=fall&gender=unisex&minimum_value=4");
    expect(discoverHref("", { mode: "balance", family: "", season: "", gender: "", minimum_value: "" })).toBe("/discover");
  });
});

describe("DiscoverAtelier", () => {
  it("shows the hero and the grid without scores", () => {
    render(<DiscoverAtelier results={results} wishlistIds={[]} />);
    const hero = screen.getByTestId("discover-hero");
    expect(within(hero).getByRole("heading", { name: "Hero Scent" })).toBeInTheDocument();
    expect(within(hero).getByText("Adds a fresh dimension to your woody shelf.")).toBeInTheDocument();
    expect(screen.getAllByTestId("fragrance-card")).toHaveLength(2);
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Second" })).toHaveAttribute("href", "/collection/00000000-0000-4000-8000-000000000001?from=discover");
  });

  it.each(["taste", "explore", "seasonal"])("loads the %s feed in live mode and writes the URL", async (mode) => {
    const user = userEvent.setup();
    render(<DiscoverAtelier results={[]} liveMode />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/api/discover/feed?mode=balance"), expect.anything()));
    const labels: Record<string, string> = { taste: "More of what I love", explore: "Explore something new", seasonal: "For the season" };
    await user.click(screen.getByRole("button", { name: new RegExp(`^${labels[mode]}`) }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining(`/api/discover/feed?mode=${mode}`), expect.anything()));
    expect(window.location.search).toBe(`?mode=${mode}`);
  });

  it("applies filters from the sheet and ignores a closed sheet", async () => {
    const user = userEvent.setup();
    render(<DiscoverAtelier results={[]} liveMode />);
    await user.click(screen.getByRole("button", { name: /Filters/ }));
    let sheet = await screen.findByRole("dialog", { name: "Filters" });
    await user.click(within(sheet).getByRole("button", { name: "Woody" }));
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(window.location.search).toBe("");
    await user.click(screen.getByRole("button", { name: /Filters/ }));
    sheet = await screen.findByRole("dialog", { name: "Filters" });
    expect(within(sheet).getByRole("button", { name: "Woody" })).toHaveAttribute("aria-pressed", "false");
    await user.click(within(sheet).getByRole("button", { name: "Woody" }));
    await user.click(within(sheet).getByRole("button", { name: "Fall" }));
    await user.click(within(sheet).getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(window.location.search).toBe("?family=Woody&season=fall"));
    expect(screen.getByRole("button", { name: /Filters · 2/ })).toBeInTheDocument();
  });

  it("hides modes and the hero while searching", async () => {
    const user = userEvent.setup();
    render(<DiscoverAtelier results={results} liveMode />);
    await user.type(screen.getByRole("searchbox"), "found");
    expect(screen.queryByRole("group", { name: "Discovery direction" })).not.toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Found" })).toBeInTheDocument();
    expect(screen.queryByTestId("discover-hero")).not.toBeInTheDocument();
  });

  it("adds to the wishlist and fills the heart", async () => {
    const user = userEvent.setup();
    render(<DiscoverAtelier results={results} wishlistIds={[]} />);
    await user.click(screen.getByRole("button", { name: "Add Second to wishlist" }));
    await waitFor(() => expect(server.addToWishlist).toHaveBeenCalled());
    expect((server.addToWishlist.mock.calls[0][0] as FormData).get("fragrance_id")).toBe("00000000-0000-4000-8000-000000000001");
    expect(await screen.findByRole("button", { name: "Second is on your wishlist" })).toHaveAttribute("aria-pressed", "true");
  });

  it("disables hearts when wishlist status fails", async () => {
    fetchMock.mockImplementation(async (url: string) => url.startsWith("/api/discover/wishlist") ? new Response("{}", { status: 503 }) : new Response(JSON.stringify({ items: results }), { status: 200 }));
    render(<DiscoverAtelier results={[]} liveMode />);
    expect(await screen.findByText("Wishlist status is temporarily unavailable. Hearts return when it is back.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "Add Second to wishlist" })).toBeDisabled());
  });

  it("keeps search available when the feed fails", async () => {
    fetchMock.mockImplementation(async (url: string) => url.startsWith("/api/discover/feed") ? new Response("{}", { status: 503 }) : new Response(JSON.stringify([]), { status: 200 }));
    render(<DiscoverAtelier results={[]} liveMode />);
    expect(await screen.findByText("Your recommendations could not be loaded. You can still search the catalog or retry.")).toBeInTheDocument();
    expect(screen.getByRole("searchbox")).toBeEnabled();
  });

  it("navigates in server mode", async () => {
    const user = userEvent.setup();
    render(<DiscoverAtelier results={results} />);
    await user.click(screen.getByRole("button", { name: /^Explore something new/ }));
    expect(router.push).toHaveBeenCalledWith("/discover?mode=explore");
  });
});
