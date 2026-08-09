import { describe, expect, it, vi } from "vitest";

import { getApiAvailability } from "./api-status";

describe("getApiAvailability", () => {
  it("returns available for an ok liveness response", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(null, { status: 200 }));

    await expect(
      getApiAvailability(fetcher, "http://api:8000"),
    ).resolves.toBe("available");
    expect(fetcher).toHaveBeenCalledWith(
      "http://api:8000/health/live",
      expect.objectContaining({
        cache: "no-store",
        signal: expect.any(AbortSignal),
      }),
    );
  });

  it.each([503, 500])("returns unavailable for HTTP %s", async (status) => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(null, { status }));

    await expect(
      getApiAvailability(fetcher, "http://api:8000"),
    ).resolves.toBe("unavailable");
  });

  it("returns unavailable when the request fails", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockRejectedValue(new Error("private hostname"));

    await expect(
      getApiAvailability(fetcher, "http://api:8000"),
    ).resolves.toBe("unavailable");
  });

  it("normalizes trailing slashes in the API base URL", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response(null, { status: 200 }));

    await getApiAvailability(fetcher, "http://api:8000///");

    expect(fetcher).toHaveBeenCalledWith(
      "http://api:8000/health/live",
      expect.any(Object),
    );
  });

  it("returns unavailable without requesting when no API base URL is configured", async () => {
    const fetcher = vi.fn<typeof fetch>();

    await expect(getApiAvailability(fetcher)).resolves.toBe("unavailable");
    expect(fetcher).not.toHaveBeenCalled();
  });
});
