import { afterEach, describe, expect, it, vi } from "vitest";

import { GET } from "./route";

describe("GET /api/status", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
  });

  it("returns available from the configured internal API", async () => {
    vi.stubEnv("API_INTERNAL_URL", "http://private-api:8000");
    vi.stubEnv("NODE_ENV", "production");
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 200 }));

    const response = await GET();

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ api: "available" });
    expect(fetcher).toHaveBeenCalledWith(
      "http://private-api:8000/health/live",
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("normalizes API failure into an HTTP 200 status payload", async () => {
    vi.stubEnv("API_INTERNAL_URL", "http://private-api:8000");
    vi.stubEnv("NODE_ENV", "production");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 503 }),
    );

    const response = await GET();

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ api: "unavailable" });
  });

  it("uses localhost as the internal API only in development", async () => {
    vi.stubEnv("API_INTERNAL_URL", "");
    vi.stubEnv("NODE_ENV", "development");
    const fetcher = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 200 }));

    await GET();

    expect(fetcher).toHaveBeenCalledWith(
      "http://localhost:8000/health/live",
      expect.any(Object),
    );
  });

  it("reports unavailable without an internal API URL in production", async () => {
    vi.stubEnv("API_INTERNAL_URL", "");
    vi.stubEnv("NODE_ENV", "production");
    const fetcher = vi.spyOn(globalThis, "fetch");

    const response = await GET();

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ api: "unavailable" });
    expect(fetcher).not.toHaveBeenCalled();
  });
});
