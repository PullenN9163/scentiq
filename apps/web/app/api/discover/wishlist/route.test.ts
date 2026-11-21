// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiClient, ApiError } from "@/lib/server/api-client";
import { GET } from "./route";

vi.mock("@/lib/server/api-client",()=>({apiClient:{get:vi.fn()},ApiError:class ApiError extends Error{constructor(readonly kind:string,readonly status:number,readonly body:{code:string;message:string}){super(body.message);}}}));
afterEach(()=>vi.resetAllMocks());

describe("Discover wishlist BFF",()=>{
  it("returns only wishlist fragrance IDs and uses private no-store headers",async()=>{
    vi.mocked(apiClient.get).mockResolvedValue([{status:"wishlist",fragrance:{id:"saved"}},{status:"owned",fragrance:{id:"owned"}}]);
    const response=await GET(new Request("https://app.example/api/discover/wishlist"));
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    expect(await response.json()).toEqual(["saved"]);
  });
  it("maps expired sessions to a safe message",async()=>{
    vi.mocked(apiClient.get).mockRejectedValue(new ApiError("unauthorized",401,{code:"private_detail",message:"raw backend detail"}));
    const response=await GET(new Request("https://app.example/api/discover/wishlist"));
    expect(response.status).toBe(401);
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    expect(await response.json()).toEqual({message:"Sign in again to continue."});
  });
});
