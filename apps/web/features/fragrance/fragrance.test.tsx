import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fragranceDetail, fragranceSummary } from "@/test/catalog-fixtures";
import type { CollectionItem, FragrancePageData } from "@/types/api";
import type { LayeringStackSuggestion } from "@/types/layering";

import { actionsFor, ownershipOf } from "./fragrance-actions";
import { FragranceContent } from "./fragrance-content";
import { notesByStage, personalLine, weeklyWears } from "./fragrance-copy";
import { FragranceListProvider, useRegisterFragranceList } from "./fragrance-list-context";
import { FragranceSheetFrame } from "./fragrance-sheet-frame";
import { layeringPartners } from "./layers-well-with";

const router = vi.hoisted(() => ({ back: vi.fn(), replace: vi.fn(), refresh: vi.fn(), push: vi.fn() }));
const server = vi.hoisted(() => ({
  addToCollection: vi.fn(),
  addToWishlist: vi.fn(),
  logWear: vi.fn(),
  updateCollectionItem: vi.fn(),
}));
vi.mock("next/navigation", () => ({ useRouter: () => router, usePathname: () => "/collection/f1" }));
vi.mock("@/lib/server/actions", () => server);

const fragrance = fragranceDetail({ id: "f1", name: "Another 13", top_accords: ["Musky"] });
const owned: CollectionItem = { id: "item1", fragrance, ownership_type: "bottle", status: "owned", bottle_size_ml: 100, remaining_ml: 60, user_rating: 4, purchase_price: "120.00", purchase_date: null, custom_longevity: null, custom_projection: null };

function data(overrides: Partial<FragrancePageData> = {}): FragrancePageData {
  return { fragrance, collection_item: owned, recent_wears: [], ...overrides };
}

beforeEach(() => {
  server.addToCollection.mockResolvedValue({ status: "success", message: "Added to your collection." });
  server.addToWishlist.mockResolvedValue(undefined);
  server.updateCollectionItem.mockResolvedValue({ status: "success", message: "Collection item updated." });
  server.logWear.mockResolvedValue({ status: "success", message: "Wear logged." });
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: false, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
});
afterEach(() => { vi.clearAllMocks(); vi.unstubAllGlobals(); });

describe("action matrix", () => {
  it.each([
    ["owned", { primary: "wear", secondary: "layer", menu: ["edit", "rate", "finish"] }],
    ["wishlist", { primary: "own", secondary: "layer", menu: [] }],
    ["none", { primary: "wishlist", secondary: "own", menu: [] }],
    ["retired", { primary: null, secondary: "layer", menu: ["edit", "rate"] }],
  ] as const)("%s", (ownership, expected) => {
    expect(actionsFor(ownership)).toEqual(expected);
  });

  it("maps collection statuses", () => {
    expect(ownershipOf(null)).toBe("none");
    expect(ownershipOf({ status: "owned" })).toBe("owned");
    expect(ownershipOf({ status: "wishlist" })).toBe("wishlist");
    expect(ownershipOf({ status: "finished" })).toBe("retired");
    expect(ownershipOf({ status: "sold" })).toBe("retired");
  });

  it("shows Wear it and Layer it for an owned fragrance", () => {
    render(<FragranceContent data={data()} variant="sheet" />);
    expect(screen.getByRole("button", { name: "Wear it" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Layer it" })).toHaveAttribute("href", "/layering?a=f1");
    expect(screen.getByRole("button", { name: "More actions" })).toBeInTheDocument();
  });

  it("moves a wishlist fragrance to the shelf, keeping its other values", async () => {
    const user = userEvent.setup();
    render(<FragranceContent data={data({ collection_item: { ...owned, status: "wishlist" } })} variant="sheet" />);
    await user.click(screen.getByRole("button", { name: "I own this" }));
    await waitFor(() => expect(server.updateCollectionItem).toHaveBeenCalled());
    const form = server.updateCollectionItem.mock.calls[0][1] as FormData;
    expect(Object.fromEntries(form)).toEqual({ item_id: "item1", ownership_type: "bottle", status: "owned", remaining_ml: "60", purchase_price: "120.00", user_rating: "4" });
  });

  it("adds a catalog fragrance to the wishlist or the shelf", async () => {
    const user = userEvent.setup();
    render(<FragranceContent data={data({ collection_item: null })} variant="sheet" />);
    await user.click(screen.getByRole("button", { name: "Add to wishlist" }));
    await waitFor(() => expect(server.addToWishlist).toHaveBeenCalled());
    expect((server.addToWishlist.mock.calls[0][0] as FormData).get("fragrance_id")).toBe("f1");
  });

  it("adds a catalog fragrance as owned with I own this", async () => {
    const user = userEvent.setup();
    render(<FragranceContent data={data({ collection_item: null })} variant="sheet" />);
    await user.click(screen.getByRole("button", { name: "I own this" }));
    await waitFor(() => expect(server.addToCollection).toHaveBeenCalled());
    expect(Object.fromEntries(server.addToCollection.mock.calls[0][1] as FormData)).toEqual({ fragrance_id: "f1", status: "owned", ownership_type: "bottle" });
  });

  it("shows an inline error with a retry", async () => {
    const user = userEvent.setup();
    server.addToWishlist.mockRejectedValueOnce(new Error("nope"));
    render(<FragranceContent data={data({ collection_item: null })} variant="sheet" />);
    await user.click(screen.getByRole("button", { name: "Add to wishlist" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not add it to your wishlist. Try again.");
    await user.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(server.addToWishlist).toHaveBeenCalledTimes(2));
  });

  it("logs a wear with the existing form fields", async () => {
    const user = userEvent.setup();
    render(<FragranceContent data={data()} variant="sheet" />);
    await user.click(screen.getByRole("button", { name: "Wear it" }));
    const sheet = await screen.findByRole("dialog", { name: "Wear Another 13" });
    await user.type(within(sheet).getByLabelText("Sprays"), "3");
    await user.click(screen.getByRole("button", { name: "Log wear" }));
    await waitFor(() => expect(server.logWear).toHaveBeenCalled());
    const form = server.logWear.mock.calls[0][1] as FormData;
    expect([...form.keys()].sort()).toEqual(["collection_item_id", "notes", "occasion", "setting", "sprays", "worn_at"]);
    expect(form.get("collection_item_id")).toBe("item1");
    expect(form.get("sprays")).toBe("3");
  });
});

describe("sections", () => {
  it("leaves out sections with no data", () => {
    render(<FragranceContent data={data({ fragrance: { ...fragrance, notes: [], accords: [], similar: [], description: null } })} variant="sheet" />);
    expect(screen.queryByRole("heading", { name: "Notes" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Character" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Your wears/ })).not.toBeInTheDocument();
    expect(screen.queryByText(/Not recorded/)).not.toBeInTheDocument();
  });

  it("shows notes by stage, the character strip and wears", () => {
    const now = new Date();
    render(
      <FragranceContent
        variant="page"
        data={data({
          fragrance: { ...fragrance, notes: [{ id: "n1", name: "Pear", slug: "pear", stage: "top", weight: null }, { id: "n2", name: "Musk", slug: "musk", stage: "base", weight: null }], accords: [{ id: "a", name: "Musky", slug: "musky", weight: 0.6 }, { id: "b", name: "Woody", slug: "woody", weight: 0.4 }], similar: [fragranceSummary({ id: "s1", name: "Santal 33" })] },
          recent_wears: [{ id: "w1", collection_item_id: "item1", fragrance_id: "f1", fragrance_name: "Another 13", brand_name: "Le Labo", worn_at: now.toISOString(), sprays: 3, occasion: null, setting: null, notes: null }],
        })}
      />,
    );
    expect(screen.getByText("Top")).toBeInTheDocument();
    expect(screen.getByText("Base")).toBeInTheDocument();
    expect(screen.getByText("Musky 60% · Woody 40%")).toBeInTheDocument();
    expect(screen.getByText("1 in 12 weeks")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Santal 33" })).toHaveAttribute("href", "/collection/s1");
    expect(screen.getByText("Worn 1 time, last today.")).toBeInTheDocument();
  });

  it("keeps Smells like on the full page only", () => {
    render(<FragranceContent data={data({ fragrance: { ...fragrance, similar: [fragranceSummary({ id: "s1", name: "Santal 33" })] } })} variant="sheet" />);
    expect(screen.queryByText("Smells like")).not.toBeInTheDocument();
  });
});

function Register({ ids }: { ids: string[] }) {
  useRegisterFragranceList(ids);
  return null;
}

describe("sheet stepping", () => {
  it("steps through the list that opened it", async () => {
    const user = userEvent.setup();
    render(
      <FragranceListProvider>
        <Register ids={["f0", "f1", "f2"]} />
        <FragranceSheetFrame id="f1" title="Another 13" fullHref="/collection/f1"><p>Body</p></FragranceSheetFrame>
      </FragranceListProvider>,
    );
    expect(await screen.findByText("2 of 3")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next fragrance" }));
    expect(router.replace).toHaveBeenCalledWith("/collection/f2", { scroll: false });
    await user.click(screen.getByRole("button", { name: "Previous fragrance" }));
    expect(router.replace).toHaveBeenCalledWith("/collection/f0", { scroll: false });
    expect(screen.getByRole("link", { name: /Open full page/ })).toHaveAttribute("href", "/collection/f1");
  });

  it("hides the arrows when opened from a single item, and closes with back", async () => {
    const user = userEvent.setup();
    function Empty() { useEffect(() => {}, []); return null; }
    render(<FragranceListProvider><Empty /><FragranceSheetFrame id="f1" title="Another 13" fullHref="/collection/f1"><p>Body</p></FragranceSheetFrame></FragranceListProvider>);
    expect(screen.queryByRole("button", { name: "Next fragrance" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close Another 13" }));
    expect(router.back).toHaveBeenCalled();
  });
});

describe("helpers", () => {
  it("groups notes and skips empty stages", () => {
    expect(notesByStage([{ id: "1", name: "Musk", slug: "m", stage: "base", weight: null }])).toEqual([{ label: "Base", notes: ["Musk"] }]);
  });

  it("buckets wears into twelve weeks", () => {
    const now = new Date("2026-11-14T12:00:00Z");
    const wear = (iso: string) => ({ id: iso, collection_item_id: "i", fragrance_id: "f", fragrance_name: "", brand_name: "", worn_at: iso, sprays: null, occasion: null, setting: null, notes: null });
    const weeks = weeklyWears([wear("2026-11-13T12:00:00Z"), wear("2026-11-01T12:00:00Z"), wear("2026-01-01T12:00:00Z")], 12, now);
    expect(weeks).toHaveLength(12);
    expect(weeks[11]).toBe(1);
    expect(weeks.reduce((a, b) => a + b, 0)).toBe(2);
  });

  it("falls back from wears to status to catalog facts", () => {
    expect(personalLine(fragrance, owned, [])).toBe("On your shelf, not worn yet.");
    expect(personalLine({ ...fragrance, concentration: "Eau de Parfum", release_year: 2010 }, null, [])).toBe("Eau de Parfum · 2010");
    expect(personalLine({ ...fragrance, concentration: null, release_year: null }, null, [])).toBeNull();
  });

  it("picks up to three distinct partners", () => {
    const suggestion = (ids: string[], score: number) => ({ score, mode: "balanced", items: ids.map((id, index) => ({ fragrance: fragranceSummary({ id, name: id }), role: "anchor", application_order: index + 1, suggested_sprays: 1 })) }) as unknown as LayeringStackSuggestion;
    const partners = layeringPartners("a", [suggestion(["a", "b"], 0.5), suggestion(["a", "c", "b"], 0.9), suggestion(["d", "e"], 0.1)]);
    expect(partners.map((partner) => partner.fragrance.id)).toEqual(["c", "b", "d"]);
  });
});
