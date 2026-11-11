// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiClient, ApiError } from "@/lib/server/api-client";
import { GET } from "./route";

vi.mock("@/lib/server/api-client", () => ({
  apiClient: { get: vi.fn() },
  ApiError: class ApiError extends Error { constructor(readonly kind:string, readonly status:number, readonly body:{code:string;message:string}) { super(body.message); } get code(){return this.body.code;} },
}));
afterEach(()=>vi.resetAllMocks());

describe("Discover search BFF",()=>{
  it("bounds the query and page size and forwards active filters with an abort signal",async()=>{
    vi.mocked(apiClient.get).mockResolvedValue([]);
    const response=await GET(new Request("https://app.example/api/discover/search?q=%20amber%20&limit=500&offset=25&family=Woody&gender=unisex&season=fall&minimum_value=4"));
    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    const [path, options]=vi.mocked(apiClient.get).mock.calls[0]!;
    expect(path).toBe("/api/v1/fragrances?q=amber&limit=50&offset=25&sort=relevance&family=Woody&gender=unisex&season=fall&minimum_value=4");
    expect(options?.signal).toBeInstanceOf(AbortSignal);
  });
  it("does not leak upstream details and keeps private no-store headers on failures",async()=>{
    vi.mocked(apiClient.get).mockRejectedValue(new ApiError("unauthorized",401,{code:"secret",message:"internal diagnostics"}));
    const response=await GET(new Request("https://app.example/api/discover/search?q=amber"));
    expect(response.status).toBe(401);
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    expect(await response.json()).toEqual({message:"Sign in again to continue."});
  });
  it("rejects missing or unsafe pagination before calling the API",async()=>{
    expect((await GET(new Request("https://app.example/api/discover/search?q="))).status).toBe(400);
    expect((await GET(new Request("https://app.example/api/discover/search?q=amber&offset=-1"))).status).toBe(400);
    expect(apiClient.get).not.toHaveBeenCalled();
  });
});
