import { beforeEach, describe, expect, it, vi } from "vitest";
import { GET, PUT, DELETE } from "./route";
const { getToken, fetcher } = vi.hoisted(() => ({ getToken: vi.fn(), fetcher: vi.fn() }));
vi.mock("@clerk/nextjs/server", () => ({ auth: async () => ({ getToken }) }));
vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));
const id = "11111111-1111-4111-8111-111111111111";
const context = { params: Promise.resolve({ id }) };
describe("private image BFF", () => {
  beforeEach(() => { vi.stubEnv("API_INTERNAL_URL", "http://private.test"); vi.stubGlobal("fetch", fetcher); fetcher.mockReset(); getToken.mockResolvedValue("session-token"); });
  it("refuses anonymous reads without fetching storage", async () => {
    getToken.mockResolvedValue(null);
    expect((await GET(new Request(`https://scentiq.test/api/fragrances/${id}/image`), context)).status).toBe(401);
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("blocks cross-origin mutations", async () => {
    expect((await DELETE(new Request(`https://scentiq.test/api/fragrances/${id}/image`, { method: "DELETE", headers: { origin: "https://other.test" } }), context)).status).toBe(403);
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("rejects an oversized file before forwarding it", async () => {
    const response = await PUT(new Request(`https://scentiq.test/api/fragrances/${id}/image`, { method: "PUT", headers: { origin: "https://scentiq.test", "content-type": "image/png" }, body: new Uint8Array(5 * 1024 * 1024 + 1) }), context);
    expect(response.status).toBe(413);
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("authenticates a mediated private read and disables public caching", async () => {
    fetcher.mockResolvedValue(new Response(new Uint8Array([1, 2]), { headers: { "content-type": "image/webp" } }));
    const response = await GET(new Request(`https://scentiq.test/api/fragrances/${id}/image`), context);
    expect(fetcher).toHaveBeenCalledWith(`http://private.test/api/v1/fragrances/${id}/image`, expect.objectContaining({ headers: { Authorization: "Bearer session-token" }, cache: "no-store" }));
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    expect(new Uint8Array(await response.arrayBuffer())).toEqual(new Uint8Array([1, 2]));
  });
});
