// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient, ApiError } from "@/lib/server/api-client";
import { POST } from "./route";

vi.mock("@/lib/server/api-client", () => ({
  apiClient: { stream: vi.fn() },
  ApiError: class ApiError extends Error {
    constructor(readonly kind: string, readonly status: number, readonly body: { code: string; message: string }) { super(body.message); }
    get code() { return this.body.code; }
  },
}));
afterEach(() => vi.resetAllMocks());

describe("Agent BFF", () => {
  it("forwards only to authenticated internal API and passes NDJSON through unchanged", async () => {
    const bytes = '{"type":"text_delta","delta":"hello"}\n{"type":"done"}\n';
    vi.mocked(apiClient.stream).mockResolvedValue(new Response(bytes));
    const response = await POST(new Request("https://app.example/api/agent/chat", { method: "POST", headers: {origin:"https://app.example"}, body: JSON.stringify({ message: "wear today", history: [] }) }));
    expect(await response.text()).toBe(bytes);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(response.headers.get("content-type")).toBe("application/x-ndjson");
    expect(apiClient.stream).toHaveBeenCalledWith("/api/v1/agent/chat", { message: "wear today", history: [] }, expect.any(AbortSignal));
  });
  it("bounds actual request bytes and refuses malformed JSON before forwarding", async () => {
    expect((await POST(new Request("https://app.example/api/agent/chat", { method: "POST", headers: {origin:"https://app.example"}, body: "x".repeat(65537) }))).status).toBe(413);
    expect((await POST(new Request("https://app.example/api/agent/chat", { method: "POST", headers: {origin:"https://app.example"}, body: "broken" }))).status).toBe(400);
    expect(apiClient.stream).not.toHaveBeenCalled();
  });
  it("handles expired sessions without exposing upstream debug details", async () => {
    vi.mocked(apiClient.stream).mockRejectedValue(new ApiError("unauthorized", 401, { code: "unauthorized", message: "Sign in again to continue." }));
    const response = await POST(new Request("https://app.example/api/agent/chat", { method: "POST", headers: {origin:"https://app.example"}, body: '{"message":"hello"}' }));
    expect(response.status).toBe(401);
    expect(await response.json()).toEqual({ code: "unauthorized", message: "Sign in again to continue." });
  });
});

it("refuses cross-site advisor requests before calling the internal API", async () => {
 const response=await POST(new Request("https://app.example/api/agent/chat",{method:"POST",headers:{origin:"https://other.example"},body:'{"message":"today"}'}));
 expect(response.status).toBe(403);
 expect(apiClient.stream).not.toHaveBeenCalled();
});
