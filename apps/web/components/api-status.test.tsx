import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiStatus } from "./api-status";

describe("ApiStatus", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows checking before reporting an available API", async () => {
    let resolveResponse: (response: Response) => void = () => undefined;
    const response = new Promise<Response>((resolve) => {
      resolveResponse = resolve;
    });
    const fetcher = vi.spyOn(globalThis, "fetch").mockReturnValue(response);

    render(<ApiStatus />);

    expect(screen.getByRole("status")).toHaveTextContent("Checking API");

    await act(async () => {
      resolveResponse(
        new Response(JSON.stringify({ api: "available" }), {
          headers: { "content-type": "application/json" },
        }),
      );
    });

    expect(screen.getByRole("status")).toHaveTextContent("API available");
    expect(fetcher).toHaveBeenCalledWith(
      "/api/status",
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("reports an unavailable API payload", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ api: "unavailable" }), {
        headers: { "content-type": "application/json" },
      }),
    );

    render(<ApiStatus />);

    expect(await screen.findByText("API unavailable")).toBeVisible();
  });

  it("reports unavailable when the same-origin request fails", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("offline"));

    render(<ApiStatus />);

    expect(await screen.findByText("API unavailable")).toBeVisible();
  });
});
