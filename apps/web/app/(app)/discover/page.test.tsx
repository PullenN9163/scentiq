import {render,screen} from "@testing-library/react";
import {beforeEach,expect,it,vi} from "vitest";
const mocks=vi.hoisted(()=>({collection:vi.fn(),discover:vi.fn(),search:vi.fn(),redirect:vi.fn((url:string)=>{throw new Error(`redirect:${url}`);})}));
vi.mock("@/lib/server/queries",()=>({getCollection:mocks.collection,searchFragrances:mocks.search}));
vi.mock("@/lib/server/layering-actions",()=>({getDiscoveryIntelligence:mocks.discover}));
vi.mock("next/navigation",()=>({redirect:mocks.redirect}));
vi.mock("@/lib/server/api-client",()=>({ApiError:class extends Error {kind:string;status:number;code:string;constructor(kind:string,status:number,body:{message:string;code:string}){super(body.message);this.kind=kind;this.status=status;this.code=body.code;}}}));
import DiscoverPage from "./page";
import {ApiError} from "@/lib/server/api-client";
beforeEach(()=>{vi.clearAllMocks();mocks.collection.mockResolvedValue([]);mocks.discover.mockResolvedValue([]);mocks.search.mockResolvedValue([]);});
it("keeps catalog search and filters available after recommendation failure",async()=>{
  mocks.discover.mockRejectedValue(new ApiError("unavailable",503,{code:"service_timeout",message:"timeout"}));
  render(await DiscoverPage({searchParams:Promise.resolve({family:"Woody",gender:"unisex",minimum_value:"4"})}));
  expect(screen.getByRole("searchbox")).toBeVisible();
  expect(screen.getByRole("alert")).toHaveTextContent("could not be loaded");
  expect(screen.getByLabelText("Family")).toHaveValue("Woody");
});
it("redirects expired sessions instead of disguising them as empty results",async()=>{
  mocks.collection.mockRejectedValue(new ApiError("unauthorized",401,{code:"unauthorized",message:"expired"}));
  await expect(DiscoverPage({searchParams:Promise.resolve({})})).rejects.toThrow("redirect:/sign-in");
});
it("does not convert forbidden access into a successful empty response",async()=>{
  mocks.discover.mockRejectedValue(new ApiError("forbidden",403,{code:"forbidden",message:"denied"}));
  await expect(DiscoverPage({searchParams:Promise.resolve({})})).rejects.toMatchObject({kind:"forbidden"});
});
it("continues catalog search but disables uncertain wishlist saves if collection data is unavailable",async()=>{
  mocks.collection.mockRejectedValue(new Error("offline"));
  render(await DiscoverPage({searchParams:Promise.resolve({q:"cedar"})}));
  expect(mocks.search).toHaveBeenCalledWith("cedar");
  expect(mocks.discover).not.toHaveBeenCalled();
  expect(screen.getByRole("searchbox")).toHaveValue("cedar");
  expect(screen.getByRole("status")).toHaveTextContent("Wishlist status");
});
