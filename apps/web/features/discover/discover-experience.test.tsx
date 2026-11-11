vi.mock("@/lib/server/surface-choice-actions",()=>({surfaceChoice:vi.fn().mockResolvedValue({ok:false,error:""})}));
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { discoveryResult, fragranceSummary } from "@/test/catalog-fixtures";

import { DiscoverExperience } from "./discover-experience";
import userEvent from "@testing-library/user-event";
import { searchCatalogPage } from "@/lib/server/actions";

vi.mock("@/lib/server/actions", () => ({
  addToWishlist: vi.fn(),
  searchCatalogPage: vi.fn().mockResolvedValue([]),
}));

afterEach(()=>{cleanup();vi.useRealTimers();vi.unstubAllGlobals();});

describe("DiscoverExperience", () => {
  it("offers discovery directions while preserving active filters",()=>{
    render(<DiscoverExperience results={[discoveryResult()]} selectedFamily="Woody" selectedSeason="fall" selectedGender="unisex" selectedMinimumValue="4"/>);
    const direction=screen.getByRole("link",{name:"Explore something new"});
    expect(direction).toHaveAttribute("href","/discover?mode=explore&family=Woody&season=fall&gender=unisex&minimum_value=4");
    expect(screen.getByText("Featured discovery")).toBeVisible();
  });
  it("switches gallery density and retains entered filters when the panel closes",async()=>{
    render(<DiscoverExperience results={[discoveryResult()]}/>);
    const user=userEvent.setup();
    await user.click(screen.getByRole("button",{name:"Compact view"}));
    expect(screen.getByRole("button",{name:"Compact view"})).toHaveAttribute("aria-pressed","true");
    await user.click(screen.getByRole("button",{name:/More filters/}));
    await user.type(screen.getByLabelText("Family"),"Amber");
    await user.click(screen.getByRole("button",{name:/More filters/}));
    await user.click(screen.getByRole("button",{name:/More filters/}));
    expect(screen.getByLabelText("Family")).toHaveValue("Amber");
  });
  it("reflects all active filters", () => {
    render(<DiscoverExperience results={[]} selectedFamily="Woody" selectedGender="unisex" selectedMinimumValue="4" />);
    expect(screen.getByLabelText("Family")).toHaveValue("Woody");
    expect(screen.getByLabelText("Gender")).toHaveValue("unisex");
    expect(screen.getByLabelText("Minimum value rating")).toHaveValue("4");
  });
  it("replaces catalog results when the search changes", () => {
    const { rerender } = render(<DiscoverExperience results={[]} query="first" catalogResults={[fragranceSummary({name:"First scent"})]} />);
    rerender(<DiscoverExperience results={[]} query="second" catalogResults={[fragranceSummary({name:"Second scent"})]} />);
    expect(screen.getByRole("heading", {name:"Second scent"})).toBeVisible();
    expect(screen.queryByRole("heading", {name:"First scent"})).not.toBeInTheDocument();
    expect(screen.getByRole("searchbox")).toHaveValue("second");
  });
  it("keeps search available when recommendations fail", () => {
    render(<DiscoverExperience results={[]} recommendationError="Recommendations are unavailable. Try again." />);
    expect(screen.getByRole("searchbox")).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent("Recommendations are unavailable");
    expect(screen.queryByText("No recommendations yet")).not.toBeInTheDocument();
  });
  it("preserves matches and allows retry after pagination fails", async () => {
    vi.mocked(searchCatalogPage).mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce([]);
    const items = Array.from({length:25}, (_, index) => fragranceSummary({id:`item-${index}`,name:`Scent ${index}`}));
    render(<DiscoverExperience results={[]} query="scent" catalogResults={items} />);
    const loadMore = screen.getByText("Load more", {selector:"button"});
    fireEvent.click(loadMore);
    expect(await screen.findByText(/Could not load more/)).toBeVisible();
    expect(screen.getAllByTestId("catalog-result-card")).toHaveLength(25);
    await waitFor(()=>expect(loadMore).toBeEnabled());
    fireEvent.click(loadMore);
    await waitFor(()=>expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  },10000);
  it("shows the selected discovery direction, season and supporting reasons", () => {
    render(
      <DiscoverExperience
        mode="explore"
        selectedSeason="summer"
        results={[
          discoveryResult({
            reasons: ["A new amber profile"],
            evidence_coverage: 0.5,
          }),
        ]}
      />,
    );
    expect(screen.getByLabelText("Discovery direction")).toHaveValue("explore");
    expect(screen.getByLabelText("Season")).toHaveValue("summer");
    expect(screen.getByText("A new amber profile")).toBeVisible();
    expect(screen.getByText(/50% catalog evidence/)).toBeVisible();
  });
  it("shows an existing wishlist entry as saved and prevents another add", () => {
    render(
      <DiscoverExperience
        results={[discoveryResult()]}
        wishlistIds={["11111111-1111-4111-8111-111111111111"]}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Saved to wishlist" }),
    ).toBeDisabled();
    expect(
      screen.queryByRole("button", { name: "Add to wishlist" }),
    ).not.toBeInTheDocument();
  });
  it("renders source-backed recommendations and supported filters", () => {
    render(<DiscoverExperience results={[discoveryResult()]} />);

    expect(screen.getByRole("heading", { name: "Source Scent" })).toBeVisible();
    expect(screen.getByText("Taste match")).toBeVisible();
    expect(screen.getByText("80%")).toBeVisible();
    fireEvent.click(screen.getByRole("button", {name:/More filters/}));
    expect(screen.getByLabelText("Family")).toBeVisible();
    expect(
      screen.getByRole("button", { name: /add to wishlist/i }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "View details" })).toHaveAttribute(
      "href",
      "/collection/11111111-1111-4111-8111-111111111111?from=discover",
    );
  });

  it("is honest when no recommendation is supported", () => {
    render(<DiscoverExperience results={[]} />);

    expect(screen.getByText("No recommendations yet")).toBeVisible();
    expect(screen.getByText(/will not invent a match/i)).toBeVisible();
  });

  it("shows direct catalog matches instead of recommendation scores during search", () => {
    render(
      <DiscoverExperience
        results={[discoveryResult()]}
        query="source"
        catalogResults={[fragranceSummary({ concentration: "eau_de_parfum" })]}
      />,
    );

    expect(
      screen.getByRole("searchbox", { name: "Search the fragrance catalog" }),
    ).toHaveValue("source");
    expect(screen.getByRole("heading", { name: "Source Scent" })).toBeVisible();
    expect(screen.getByText("Eau de parfum")).toBeVisible();
    expect(screen.queryByText("Taste match")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View details" })).toHaveAttribute(
      "href",
      "/collection/11111111-1111-4111-8111-111111111111?from=discover&q=source",
    );
  });

  it("explains when catalog search has no matches", () => {
    render(
      <DiscoverExperience results={[]} query="missing" catalogResults={[]} />,
    );

    expect(screen.getByText("No fragrances found for “missing”")).toBeVisible();
    expect(screen.getByRole("link", { name: "Clear search" })).toHaveAttribute(
      "href",
      "/discover",
    );
  });

  it("debounces live search by 200ms, sends filters, and skips recommendations for a query", async()=>{
    vi.useFakeTimers();
    const fetchMock=vi.fn(async (input:RequestInfo|URL)=>new Response(JSON.stringify(String(input).includes("wishlist")?[]:[fragranceSummary({name:"Search result"})]),{status:200}));
    vi.stubGlobal("fetch",fetchMock);
    render(<DiscoverExperience results={[]} query="cedar" liveMode selectedFamily="Woody" selectedGender="unisex" selectedSeason="fall" selectedMinimumValue="4"/>);
    await act(async()=>{await vi.advanceTimersByTimeAsync(200);});
    const calls=fetchMock.mock.calls.map(call=>String(call[0]));
    expect(calls.some(url=>url.startsWith("/api/discover/feed"))).toBe(false);
    expect(calls.some(url=>url.includes("/api/discover/search?q=cedar")&&url.includes("family=Woody")&&url.includes("gender=unisex")&&url.includes("season=fall")&&url.includes("minimum_value=4"))).toBe(true);
    fireEvent.change(screen.getByRole("searchbox"),{target:{value:"cedar musk"}});
    await act(async()=>{await vi.advanceTimersByTimeAsync(199);});
    expect(fetchMock.mock.calls.filter(call=>String(call[0]).startsWith("/api/discover/search"))).toHaveLength(1);
    await act(async()=>{await vi.advanceTimersByTimeAsync(1);});
    expect(fetchMock.mock.calls.filter(call=>String(call[0]).startsWith("/api/discover/search"))).toHaveLength(2);
  });

  it("ignores an older response that arrives after a newer query", async()=>{
    const pending:Array<{resolve:(response:Response)=>void}>=[];
    const fetchMock=vi.fn((input:RequestInfo|URL)=>{
      if(String(input).includes("wishlist"))return Promise.resolve(new Response("[]"));
      return new Promise<Response>(resolve=>pending.push({resolve}));
    });
    vi.stubGlobal("fetch",fetchMock);
    render(<DiscoverExperience results={[]} query="first" liveMode/>);
    await waitFor(()=>expect(pending).toHaveLength(1));
    fireEvent.change(screen.getByRole("searchbox"),{target:{value:"second"}});
    await waitFor(()=>expect(pending).toHaveLength(2));
    await act(async()=>pending[1]!.resolve(new Response(JSON.stringify([fragranceSummary({id:"second",name:"Second result"})]))));
    expect(screen.getByRole("heading",{name:"Second result"})).toBeVisible();
    await act(async()=>pending[0]!.resolve(new Response(JSON.stringify([fragranceSummary({id:"first",name:"First result"})]))));
    expect(screen.queryByRole("heading",{name:"First result"})).not.toBeInTheDocument();
  });

  it("clear cancels the pending search and restores recommendation mode", async()=>{
    const pending:Array<{signal?:AbortSignal;resolve:(response:Response)=>void}>=[];
    const fetchMock=vi.fn((input:RequestInfo|URL,init?:RequestInit)=>{
      const url=String(input);
      if(url.includes("wishlist"))return Promise.resolve(new Response("[]"));
      if(url.includes("feed"))return Promise.resolve(new Response(JSON.stringify({items:[],refresh_status:"fresh"})));
      return new Promise<Response>(resolve=>pending.push({signal:init?.signal as AbortSignal|undefined,resolve}));
    });
    vi.stubGlobal("fetch",fetchMock);
    render(<DiscoverExperience results={[]} query="cedar" liveMode/>);
    await waitFor(()=>expect(pending).toHaveLength(1));
    const signal=pending[0]?.signal;
    fireEvent.click(screen.getByRole("link",{name:"Clear search"}));
    expect(signal?.aborted).toBe(true);
    await act(async()=>{pending[0]?.resolve(new Response(JSON.stringify([fragranceSummary({name:"Stale result"})])));});
    expect(screen.queryByRole("heading",{name:"Stale result"})).not.toBeInTheDocument();
    await waitFor(()=>expect(screen.getByText("No recommendations yet")).toBeVisible());
  });

  it("ignores pagination JSON and errors after the query changes",async()=>{
    let resolveMore:(items:ReturnType<typeof fragranceSummary>[])=>void=()=>{};
    vi.mocked(searchCatalogPage).mockReturnValueOnce(new Promise(resolve=>{resolveMore=resolve;}));
    const items=Array.from({length:25},(_,index)=>fragranceSummary({id:`page-${index}`,name:`Page scent ${index}`}));
    render(<DiscoverExperience results={[]} query="scent" catalogResults={items}/>);
    fireEvent.click(screen.getByRole("button",{name:"Load more"}));
    await waitFor(()=>expect(searchCatalogPage).toHaveBeenCalled());
    fireEvent.change(screen.getByRole("searchbox"),{target:{value:"new query"}});
    resolveMore([fragranceSummary({id:"stale-page",name:"Stale page scent"})]);
    await act(async()=>{await Promise.resolve();});
    expect(screen.queryByRole("heading",{name:"Stale page scent"})).not.toBeInTheDocument();
    expect(screen.getAllByTestId("catalog-result-card")).toHaveLength(25);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("offers sign-in recovery when live search receives an expired-session response",async()=>{
    const fetchMock=vi.fn(async(input:RequestInfo|URL)=>String(input).includes("wishlist")?new Response("[]"):new Response(JSON.stringify({message:"Sign in again"}),{status:401}));
    vi.stubGlobal("fetch",fetchMock);
    render(<DiscoverExperience results={[]} query="cedar" liveMode/>);
    expect(await screen.findByRole("link",{name:"Sign in again"})).toHaveAttribute("href","/sign-in");
    expect(screen.queryByText(/Search is temporarily unavailable/)).not.toBeInTheDocument();
  });

  it("offers sign-in recovery for expired feed and wishlist requests",async()=>{
    const requested:string[]=[];
    const fetchMock=vi.fn(async(input:RequestInfo|URL)=>{
      requested.push(String(input));
      return new Response(JSON.stringify({message:"Sign in again"}),{status:401});
    });
    vi.stubGlobal("fetch",fetchMock);
    render(<DiscoverExperience results={[]} liveMode/>);
    expect(await screen.findByRole("link",{name:"Sign in again"})).toHaveAttribute("href","/sign-in");
    expect(requested.some(url=>url.startsWith("/api/discover/feed"))).toBe(true);
    expect(requested.some(url=>url.startsWith("/api/discover/wishlist"))).toBe(true);
  });

  it("offers sign-in recovery when pagination receives an expired-session response",async()=>{
    const items=Array.from({length:25},(_,index)=>fragranceSummary({id:`auth-page-${index}`,name:`Auth scent ${index}`}));
    const fetchMock=vi.fn(async(input:RequestInfo|URL)=>String(input).includes("wishlist")?new Response("[]"):String(input).includes("offset=0")?new Response(JSON.stringify(items)):new Response(JSON.stringify({message:"Sign in again"}),{status:401}));
    vi.stubGlobal("fetch",fetchMock);
    render(<DiscoverExperience results={[]} query="scent" liveMode/>);
    fireEvent.click(await screen.findByRole("button",{name:"Load more"}));
    expect(await screen.findByRole("link",{name:"Sign in again"})).toHaveAttribute("href","/sign-in");
    expect(screen.queryByText(/Could not load more fragrances/)).not.toBeInTheDocument();
  });
});
