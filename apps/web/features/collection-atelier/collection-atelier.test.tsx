import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fragranceSummary } from "@/test/catalog-fixtures";
import type { CollectionItem } from "@/types/api";
import type { SavedLayeringStack } from "@/types/layering";

import { CollectionAtelier } from "./collection-atelier";
import { DEFAULT_FILTERS, accordsPresent, applyFilters, segmentItems, statusLine } from "./collection-filters";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }), usePathname: () => "/collection" }));
const server = vi.hoisted(() => ({ updateCollectionItem: vi.fn(), addToCollection: vi.fn(), createCustomFragrance: vi.fn(), searchCatalogPage: vi.fn(), logWear: vi.fn() }));
vi.mock("@/lib/server/actions", () => server);
const layering = vi.hoisted(() => ({ deleteLayerStack: vi.fn(), renameLayerStack: vi.fn(), logLayerStackWear: vi.fn() }));
vi.mock("@/lib/server/layering-actions", () => layering);

let counter = 0;
function item(name: string, overrides: Partial<CollectionItem> = {}, accord = "Woody", house = "House"): CollectionItem {
  counter += 1;
  return {
    id: `item-${name}`,
    fragrance: fragranceSummary({ id: `f-${counter}-${name}`, name, top_accords: [accord], brand: { id: house, name: house, slug: house, country: null } }),
    ownership_type: "bottle", status: "owned", bottle_size_ml: 100, remaining_ml: 50, user_rating: null, purchase_price: null, purchase_date: null, custom_longevity: null, custom_projection: null,
    ...overrides,
  };
}

const shelf = [
  item("Cedar", { user_rating: 3 }, "Woody", "Zeta"),
  item("Lemon", { user_rating: 5, ownership_type: "sample" }, "Citrus", "Alpha"),
  item("Unrated", {}, "Amber", "Beta"),
  item("Nearly", { remaining_ml: 5, user_rating: 1 }, "Fresh", "Gamma"),
  item("Gone", { status: "finished" }, "Woody", "Delta"),
  item("Wanted", { status: "wishlist", ownership_type: "sample" }, "Floral", "Eta"),
];

function stack(): SavedLayeringStack {
  return { id: "11111111-1111-4111-8111-1111111111aa", name: "Amber Dusk", notes: null, wear_count: 3, average_rating: 4.5, last_worn_at: null, created_at: "2026-11-01T00:00:00Z", suggestion: { items: [{ fragrance: shelf[0].fragrance, role: "anchor", application_order: 1, suggested_sprays: 2 }, { fragrance: shelf[2].fragrance, role: "accent", application_order: 2, suggested_sprays: 1 }], mode: "balanced" } } as unknown as SavedLayeringStack;
}

beforeEach(() => {
  server.updateCollectionItem.mockResolvedValue({ status: "success", message: "ok" });
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: false, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
});
afterEach(() => { vi.clearAllMocks(); vi.unstubAllGlobals(); });


describe("collection filters", () => {
  it("splits segments, with finished items only under Finished", () => {
    expect(segmentItems(shelf, "shelf").map((entry) => entry.fragrance.name)).toEqual(["Cedar", "Lemon", "Unrated", "Nearly"]);
    expect(segmentItems(shelf, "shelf", true).map((entry) => entry.fragrance.name)).toEqual(["Gone"]);
    expect(segmentItems(shelf, "wishlist").map((entry) => entry.fragrance.name)).toEqual(["Wanted"]);
  });

  it("sorts highest rated first with unrated last", () => {
    expect(applyFilters(segmentItems(shelf, "shelf"), DEFAULT_FILTERS).map((entry) => entry.fragrance.name)).toEqual(["Lemon", "Cedar", "Nearly", "Unrated"]);
  });

  it("sorts A to Z, by house and by least left", () => {
    const owned = segmentItems(shelf, "shelf");
    expect(applyFilters(owned, { ...DEFAULT_FILTERS, sort: "name" }).map((entry) => entry.fragrance.name)).toEqual(["Cedar", "Lemon", "Nearly", "Unrated"]);
    expect(applyFilters(owned, { ...DEFAULT_FILTERS, sort: "house" }).map((entry) => entry.fragrance.brand.name)).toEqual(["Alpha", "Beta", "Gamma", "Zeta"]);
    expect(applyFilters(owned, { ...DEFAULT_FILTERS, sort: "left" })[0].fragrance.name).toBe("Nearly");
  });

  it("filters by search, accords and format", () => {
    const owned = segmentItems(shelf, "shelf");
    expect(applyFilters(owned, { ...DEFAULT_FILTERS, query: "alpha" }).map((entry) => entry.fragrance.name)).toEqual(["Lemon"]);
    expect(applyFilters(owned, { ...DEFAULT_FILTERS, accords: ["woody", "amber"] }).map((entry) => entry.fragrance.name)).toEqual(["Cedar", "Unrated"]);
    expect(applyFilters(owned, { ...DEFAULT_FILTERS, formats: ["sample"] }).map((entry) => entry.fragrance.name)).toEqual(["Lemon"]);
    expect(accordsPresent(owned)).toEqual(["woody", "fresh", "amber", "citrus"]);
  });

  it("writes status lines", () => {
    expect(statusLine(shelf[3])).toBe("Nearly empty");
    expect(statusLine(shelf[4])).toBe("Finished");
    expect(statusLine(shelf[0])).toBeNull();
    expect(statusLine({ ...shelf[0], bottle_size_ml: null })).toBeNull();
  });
});

describe("CollectionAtelier", () => {
  function renderCollection(props: Partial<Parameters<typeof CollectionAtelier>[0]> = {}) {
    return render(<CollectionAtelier items={shelf} catalog={[]} tasteAccords={[{ label: "Woody", count: 4, share: 0.6 }, { label: "Fresh", count: 2, share: 0.4 }]} saved={[stack()]} {...props} />);
  }

  it("shows the shelf with counts, the taste strip and status lines", () => {
    renderCollection();
    expect(screen.getByRole("button", { name: "Shelf 4" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Wishlist 1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Blends 1" })).toBeInTheDocument();
    expect(screen.getByText("Woody 60% · Fresh 40%")).toBeInTheDocument();
    expect(screen.getAllByTestId("fragrance-card")).toHaveLength(4);
    expect(screen.getByText("Nearly empty")).toBeInTheDocument();
    expect(screen.queryByText(/★|\/ 5|Match/)).not.toBeInTheDocument();
  });

  it("filters with accord chips and the Finished chip, and clears", async () => {
    const user = userEvent.setup();
    renderCollection();
    await user.click(screen.getByRole("button", { name: "Citrus" }));
    await waitFor(() => expect(screen.getAllByTestId("fragrance-card")).toHaveLength(1));
    await user.click(screen.getByRole("button", { name: "Citrus" }));
    await user.click(screen.getByRole("button", { name: "Finished" }));
    await waitFor(() => expect(screen.getAllByTestId("fragrance-card")).toHaveLength(1));
    expect(screen.getByText("Finished", { selector: "span" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Finished" }));
    await user.type(screen.getByRole("searchbox"), "zzz");
    expect(await screen.findByRole("heading", { name: "Nothing matches" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    await waitFor(() => expect(screen.getAllByTestId("fragrance-card")).toHaveLength(4));
  });

  it("applies the Format group from the filters sheet", async () => {
    const user = userEvent.setup();
    renderCollection();
    await user.click(screen.getByRole("button", { name: /Filters/ }));
    const sheet = await screen.findByRole("dialog", { name: "Filters" });
    await user.click(within(sheet).getByRole("button", { name: "Sample" }));
    await user.click(within(sheet).getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(screen.getAllByTestId("fragrance-card")).toHaveLength(1));
  });

  it("shows the wishlist with I own this", async () => {
    const user = userEvent.setup();
    renderCollection();
    await user.click(screen.getByRole("button", { name: "Wishlist 1" }));
    await waitFor(() => expect(screen.getAllByTestId("fragrance-card")).toHaveLength(1));
    const card = screen.getByTestId("fragrance-card");
    expect(card).toHaveTextContent("Wishlist");
    await user.click(within(card).getByRole("button", { name: "I own this" }));
    await waitFor(() => expect(server.updateCollectionItem).toHaveBeenCalled());
    expect((server.updateCollectionItem.mock.calls[0][1] as FormData).get("status")).toBe("owned");
  });

  it("shows blends as vials with a new blend tile", async () => {
    const user = userEvent.setup();
    renderCollection();
    await user.click(screen.getByRole("button", { name: "Blends 1" }));
    expect(screen.getByRole("link", { name: "New blend" })).toHaveAttribute("href", "/layering");
    const vial = screen.getByTestId("blend-vial");
    expect(within(vial).getByRole("link", { name: "Amber Dusk" })).toHaveAttribute("href", "/layering?saved=11111111-1111-4111-8111-1111111111aa");
    expect(vial).toHaveTextContent("Cedar + Unrated · worn 3×");
  });

  it("shows the empty states", async () => {
    const user = userEvent.setup();
    const { unmount } = renderCollection({ items: [], saved: [] });
    expect(screen.getByRole("heading", { name: "Your shelf starts here" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Wishlist 0" }));
    expect(screen.getByRole("heading", { name: "Nothing on your wishlist" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Blends 0" }));
    expect(screen.getByRole("heading", { name: "No blends yet" })).toBeInTheDocument();
    unmount();
    renderCollection({ saved: null, initialSegment: "blends" });
    expect(screen.getByRole("heading", { name: "Your blends did not load" })).toBeInTheDocument();
  });

  it("hides the taste strip without accord data", () => {
    renderCollection({ tasteAccords: [] });
    expect(screen.queryByRole("link", { name: "Your taste" })).not.toBeInTheDocument();
  });

});
