import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { fragranceDetail } from "@/test/catalog-fixtures";
import type { WearRecommendation } from "@/types/wear-intelligence";
import { RecommendationCard } from "./recommendation-card";

const decide = vi.hoisted(() => vi.fn().mockResolvedValue({ok:true,data:{}}));
const wear = vi.hoisted(() => vi.fn().mockResolvedValue({ok:true,data:{id:"wear"}}));
vi.mock("@/lib/server/recommendation-actions", () => ({decideRecommendation:decide,wearRecommendation:wear}));
vi.mock("next/navigation", () => ({useRouter: () => ({refresh:vi.fn()})}));
vi.mock("@/features/collection/wear-feedback-dialog", () => ({WearFeedbackDialog: () => <p>How did it wear?</p>}));
afterEach(cleanup);
export const recommendation: WearRecommendation = {
  id:"rec1", context_key:"day:2026-10-07", recommended_for:"2026-10-07T09:00:00Z", algorithm_version:"wear-v1",
  context:{context_key:"day:2026-10-07",recommended_for:"2026-10-07T09:00:00Z",local_date:"2026-10-07",timezone:"UTC",daypart:"day",season:"fall",source:"day"},
  fragrance:fragranceDetail(),score:78,evidence_coverage:0.7,recommended_sprays:3,
  score_components:{occasion:12.5,weather:10,season:15,rotation:10},reasons:["Source-backed seasonal match"],warnings:[],
  alternatives:[{fragrance:fragranceDetail({id:"second",name:"Alternative Scent"}),score:72,evidence_coverage:0.5,recommended_sprays:4,score_components:{rotation:10},reasons:["Useful rotation"],warnings:[]}],decision:null,
};
it("shows backend score, evidence and inspectable components", async () => {
  const user=userEvent.setup(); render(<RecommendationCard recommendation={recommendation}/>);
  expect(screen.getByText("Match 78 / 100")).toBeVisible();
  expect(screen.getByText("Moderate evidence")).toBeVisible();
  await user.click(screen.getByRole("button",{name:"Why this?"}));
  expect(screen.getByText("12.5")).toBeVisible();
});
it("persists alternatives and logs the selected fragrance", async () => {
  const user=userEvent.setup(); render(<RecommendationCard recommendation={recommendation}/>);
  await user.click(screen.getByRole("button",{name:"Another Option"}));
  await user.click(screen.getByRole("button",{name:/Choose Alternative Scent/}));
  expect(decide).toHaveBeenCalledWith("rec1","replaced","second");
  await waitFor(() => expect(screen.getByRole("button", {name:"Wear This"})).toBeEnabled());
  await user.click(screen.getByRole("button",{name:"Wear This"}));
  await user.click(await screen.findByRole("button",{name:"Log wear"}));
  await waitFor(() => expect(wear).toHaveBeenCalledWith("rec1",expect.objectContaining({selected_fragrance_id:"second",sprays:4})));
  expect(await screen.findByText("How did it wear?")).toBeVisible();
});

it("keeps wear feedback open when a refreshed recommendation replaces the fingerprint", async () => {
  const user=userEvent.setup();
  const view=render(<RecommendationCard recommendation={recommendation}/>);
  expect(screen.getByRole("link", {name:"Layer It"})).toHaveAttribute("href", `/layering?a=${recommendation.fragrance.id}`);
  await user.click(screen.getByRole("button", {name:"Wear This"}));
  await user.click(await screen.findByRole("button", {name:"Log wear"}));
  expect(await screen.findByText("How did it wear?")).toBeVisible();
  view.rerender(<RecommendationCard recommendation={{...recommendation,id:"new-fingerprint",fragrance:fragranceDetail({name:"New recommendation"})}}/>);
  expect(screen.getByText("How did it wear?")).toBeVisible();
  expect(screen.getByRole("heading", {name:"New recommendation"})).toBeVisible();
});
