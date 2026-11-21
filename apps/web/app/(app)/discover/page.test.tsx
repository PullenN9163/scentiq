import { afterEach, expect, it, vi } from "vitest";
import DiscoverPage from "./page";

vi.mock("@/lib/server/queries", () => ({
  getCollection: vi.fn().mockResolvedValue([{ fragrance: { id: "owned-1" } }]),
  searchFragrances: vi.fn().mockResolvedValue([{ id: "catalog-1" }]),
}));
vi.mock("@/lib/server/layering-actions", () => ({
  getDiscoveryIntelligence: vi.fn().mockResolvedValue([{ fragrance: { id: "feed-1" } }]),
}));

afterEach(() => { vi.unstubAllEnvs(); });

it("renders a query shell without blocking on collection or recommendations", async()=>{
  const element=await DiscoverPage({searchParams:Promise.resolve({q:"  cedar  ".repeat(20),mode:"seasonal",season:"fall",family:"Woody",gender:"unisex",minimum_value:"4"})});
  expect(element.props).toMatchObject({liveMode:true,query:"  cedar  ".repeat(20).slice(0,120),mode:"seasonal",selectedSeason:"fall",selectedFamily:"Woody",selectedGender:"unisex",selectedMinimumValue:"4",results:[]});
});

it("normalizes unsupported modes and preserves the initial search query",async()=>{
  const element=await DiscoverPage({searchParams:Promise.resolve({q:"amber",mode:"legacy"})});
  expect(element.props).toMatchObject({liveMode:true,query:"amber",mode:"balance"});
});

it.each(["false", "False"])("uses authenticated server reads when fast discovery is disabled by %s", async (flag) => {
  vi.stubEnv("SCENTIQ_FAST_DISCOVERY_ENABLED", flag);
  vi.resetModules();
  const { default: page } = await import("./page");
  const element = await page({ searchParams: Promise.resolve({ q: "amber" }) });
  expect(element.props).toMatchObject({
    liveMode: false,
    query: "amber",
    catalogResults: [{ id: "catalog-1" }],
    wishlistIds: ["owned-1"],
  });
});
