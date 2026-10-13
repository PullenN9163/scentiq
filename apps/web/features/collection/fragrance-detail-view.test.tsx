import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { fragranceDetail } from "@/test/catalog-fixtures";

import { FragranceDetailView } from "./fragrance-detail-view";
import { logWear } from "@/lib/server/actions";
import type { CollectionItem } from "@/types/api";

vi.mock("@/lib/server/actions", () => ({
  logWear: vi.fn(),
  updateCollectionItem: vi.fn(),
}));
vi.mock("@/lib/server/feedback-actions", () => ({ getWearFeedback: vi.fn(), saveWearFeedback: vi.fn() }));

describe("FragranceDetailView", () => {
  it("submits an explicit wear instant and preserves the local input after a failed save", async () => {
    vi.mocked(logWear).mockImplementation(async (_previous,data)=>({status:"error",message:"Try again",values:Object.fromEntries(data) as Record<string,string>}));
    const fragrance=fragranceDetail();
    const owned:CollectionItem={id:"owned",fragrance,ownership_type:"bottle",status:"owned",bottle_size_ml:100,remaining_ml:75,user_rating:4,purchase_price:null,purchase_date:null,custom_longevity:null,custom_projection:null};
    render(<FragranceDetailView fragrance={fragrance} ownedItem={owned} wears={[]}/>);
    await userEvent.click(screen.getByRole("button",{name:/Log wear/i}));
    fireEvent.change(screen.getByLabelText("When"),{target:{value:"2026-10-13T08:30"}});
    await userEvent.click(screen.getByRole("button",{name:"Log wear"}));
    await waitFor(()=>expect(logWear).toHaveBeenCalled());
    expect(vi.mocked(logWear).mock.calls.at(-1)![1].get("worn_at")).toBe(new Date("2026-10-13T08:30").toISOString());
    expect(await screen.findByText("Try again")).toBeVisible();
    expect(screen.getByLabelText("When")).toHaveValue("2026-10-13T08:30");
  });
  it("returns a Discover visitor to their catalog search", () => {
    render(
      <FragranceDetailView
        fragrance={fragranceDetail()}
        ownedItem={null}
        wears={[]}
        backHref="/discover?q=source"
        backLabel="Back to Discover"
      />,
    );

    expect(screen.getByRole("link", { name: /Back to Discover/ })).toHaveAttribute(
      "href",
      "/discover?q=source",
    );
  });
});
