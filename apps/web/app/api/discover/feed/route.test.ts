// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiClient, ApiError } from "@/lib/server/api-client";
import { GET } from "./route";

vi.mock("@/lib/server/api-client",()=>({apiClient:{get:vi.fn()},ApiError:class ApiError extends Error{constructor(readonly kind:string,readonly status:number,readonly body:{code:string;message:string}){super(body.message);}}}));
afterEach(()=>vi.resetAllMocks());

describe("Discovery feed BFF",()=>{
  it("forwards the selected mode, filters and bounded page through the authenticated API client",async()=>{
    vi.mocked(apiClient.get).mockResolvedValue({items:[],mode:"seasonal",limit:50,offset:25,generated_at:null,refresh_status:"pending"});
    const response=await GET(new Request("https://app.example/api/discover/feed?mode=seasonal&season=fall&family=Woody&gender=unisex&minimum_value=4&limit=500&offset=25"));
    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    expect(vi.mocked(apiClient.get).mock.calls[0]?.[0]).toBe("/api/v1/discovery-feed?mode=seasonal&limit=50&offset=25&family=Woody&gender=unisex&season=fall&minimum_value=4");
  });
  it("maps authorization errors without leaking backend messages and never caches the error",async()=>{
    vi.mocked(apiClient.get).mockRejectedValue(new ApiError("forbidden",403,{code:"private_detail",message:"raw backend detail"}));
    const response=await GET(new Request("https://app.example/api/discover/feed?mode=balance"));
    expect(response.status).toBe(403);
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    expect(await response.json()).toEqual({message:"You do not have access to recommendations."});
  });
});
