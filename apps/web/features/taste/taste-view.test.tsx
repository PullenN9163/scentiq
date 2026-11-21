import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { collectionInsights, fragranceSummary } from "@/test/catalog-fixtures";
import type { CollectionItem } from "@/types/api";

import { money, notWornLine, seasonGapSentence, sharedWords, tasteCaption, tasteStatement, thinnestSeason } from "./taste-copy";
import { TasteView } from "./taste-view";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));
vi.mock("@/lib/server/actions", () => ({ logWear: vi.fn() }));

function item(id: string, name: string, accord: string, overrides: Partial<CollectionItem> = {}): CollectionItem {
  return { id: `item-${id}`, fragrance: fragranceSummary({ id, name, top_accords: [accord], image_url: "https://fimgs.net/mdimg/perfume/x.jpg" }), ownership_type: "bottle", status: "owned", bottle_size_ml: 100, remaining_ml: 50, user_rating: null, purchase_price: "120.00", purchase_date: null, custom_longevity: null, custom_projection: null, ...overrides };
}
const collection = [item("a", "Another 13", "Musky"), item("b", "Thé Noir 29", "Woody"), item("c", "Wood Sage", "Fresh")];

const insights = collectionInsights({
  total_items: 26, total_wears: 42, wears_last_30_days: 12,
  accords: [{ label: "Woody", count: 18, share: 0.38 }, { label: "Fresh", count: 12, share: 0.25 }, { label: "Amber", count: 8, share: 0.17 }],
  most_worn: [{ collection_item_id: "item-a", fragrance_id: "a", fragrance_name: "Another 13", brand_name: "Le Labo", wear_count: 22 }],
  neglected: [{ collection_item_id: "item-c", fragrance_id: "c", fragrance_name: "Wood Sage", brand_name: "Jo Malone", wear_count: 0, last_worn_at: null, user_rating: null, cost_per_wear: null }],
  seasons: [{ label: "Spring", count: 12, share: 0.25 }, { label: "Summer", count: 3, share: 0.06 }, { label: "Fall", count: 18, share: 0.38 }, { label: "Winter", count: 14, share: 0.3 }],
  season_gaps: ["summer"],
  redundancy_pairs: [{ first_id: "b", first_name: "Thé Noir 29", second_id: "c", second_name: "Wood Sage", overlap: 0.82, shared_accords: ["Cedar", "Tea"] }],
  priced_items: 1,
  cost_per_wear: [{ collection_item_id: "item-a", fragrance_id: "a", fragrance_name: "Another 13", brand_name: "Le Labo", wear_count: 4, last_worn_at: null, user_rating: null, cost_per_wear: "30.00" }],
});

beforeEach(() => vi.stubGlobal("matchMedia", (query: string) => ({ matches: false, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
afterEach(() => { vi.clearAllMocks(); vi.unstubAllGlobals(); });

describe("taste copy", () => {
  it("words the statement for one, two and many accords", () => {
    expect(tasteStatement([])).toBeNull();
    expect(tasteStatement([{ label: "Woody", count: 1, share: 1 }])).toBe("Mostly woody.");
    expect(tasteStatement([{ label: "Fresh", count: 1, share: 0.2 }, { label: "Woody", count: 2, share: 0.5 }])).toBe("Mostly woody and fresh.");
    expect(tasteStatement(insights.accords)).toBe("Mostly woody and fresh.");
  });

  it("writes captions and lines in words", () => {
    expect(tasteCaption(insights)).toBe("26 fragrances · 42 wears · 12 in the last 30 days");
    expect(notWornLine(null)).toBe("Not worn yet");
    expect(notWornLine("2026-09-15T00:00:00Z", new Date("2026-11-14T00:00:00Z"))).toBe("Not worn in 60 days");
    expect(thinnestSeason(insights.seasons)).toBe("Summer");
    expect(seasonGapSentence(["summer", "winter"])).toBe("Your shelf is thin for summer and winter.");
    expect(sharedWords(["Cedar", "Tea"])).toBe("share cedar and tea");
    expect(money("120.00")).toBe("120");
    expect(money("29.5")).toBe("29.50");
  });
});

describe("TasteView", () => {
  it("joins insight entries to the collection for plates", () => {
    render(<TasteView insights={insights} collection={collection} />);
    expect(screen.getByRole("heading", { name: "Mostly woody and fresh." })).toBeInTheDocument();
    const overlooked = screen.getByRole("heading", { name: "Overlooked" }).closest("section")!;
    expect(within(overlooked).getByTestId("fragrance-card")).toHaveTextContent("Wood Sage");
    expect(within(overlooked).getByTestId("fragrance-card")).toHaveTextContent("Not worn yet");
    expect(overlooked.querySelector("[data-photo='true']")).not.toBeNull();
    expect(screen.getByText("and Wood Sage share cedar and tea")).toBeInTheDocument();
    expect(screen.getByText("82% overlap")).toBeInTheDocument();
    expect(screen.getByText("30 a wear")).toBeInTheDocument();
    expect(screen.getByText("Summer")).toBeInTheDocument();
    expect(screen.getByText("Your shelf is thin for summer.")).toBeInTheDocument();
  });

  it("lists an accord's fragrances and explains the counting", async () => {
    const user = userEvent.setup();
    render(<TasteView insights={insights} collection={collection} />);
    await user.click(screen.getByRole("button", { name: /Woody 38%/ }));
    const sheet = await screen.findByRole("dialog", { name: "Woody on your shelf" });
    expect(within(sheet).getByText("Thé Noir 29")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: "How this is counted" }));
    expect(await screen.findByText(/not the percentage of bottles/)).toBeInTheDocument();
  });

  it("hides sections without data", () => {
    render(<TasteView insights={{ ...insights, neglected: [], least_worn: [], redundancy_pairs: [], priced_items: 0 }} collection={collection} />);
    expect(screen.queryByRole("heading", { name: "Overlooked" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "These two smell alike" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Cost per wear" })).not.toBeInTheDocument();
  });

  it("shows only the ring and legend before any wears", () => {
    render(<TasteView insights={{ ...insights, total_wears: 0 }} collection={collection} />);
    expect(screen.getByText("Wear a few fragrances and your habits appear here.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "What you reach for" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Season coverage" })).not.toBeInTheDocument();
  });

  it("asks for more details when nothing is classified", () => {
    render(<TasteView insights={{ ...insights, unclassified_items: 26 }} collection={collection} />);
    expect(screen.getByRole("heading", { name: "ScentIQ needs a few more details about your fragrances." })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Collection" })).toHaveAttribute("href", "/collection");
  });
});
