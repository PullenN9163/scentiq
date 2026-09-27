import { beforeEach, describe, expect, it, vi } from "vitest";

const post = vi.fn();

vi.mock("@/lib/server/api-client", () => {
  class ApiError extends Error {
    constructor(
      readonly kind: string,
      readonly status: number,
      readonly body: { code: string; message: string },
    ) {
      super(body.message);
    }
    get code(): string {
      return this.body.code;
    }
  }
  return { ApiError, apiClient: { post: (...args: unknown[]) => post(...args) } };
});

const { ApiError } = await import("@/lib/server/api-client");
const { GET: start } = await import("./start/route");
const { GET: callback } = await import("./callback/route");

function params(provider: string) {
  return { params: Promise.resolve({ provider }) };
}

function location(response: Response): URL {
  const header = response.headers.get("location") ?? "";
  // Settings redirects are relative, so the browser keeps the public host.
  return new URL(header, "https://public.example");
}

describe("calendar OAuth routes", () => {
  beforeEach(() => {
    post.mockReset();
  });

  it("start redirects to the provider consent page", async () => {
    post.mockResolvedValue({ authorization_url: "https://accounts.google.com/o/oauth2/v2/auth?x=1" });

    const response = await start(
      new Request("https://app.test/integrations/calendar/google/start"),
      params("google"),
    );

    expect(post).toHaveBeenCalledWith("/api/v1/calendar/connections/google/authorize");
    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toBe(
      "https://accounts.google.com/o/oauth2/v2/auth?x=1",
    );
  });

  it("start sends an unconfigured provider back to Settings", async () => {
    post.mockImplementation(async () => {
      throw new ApiError("unavailable", 503, {
        code: "calendar_provider_not_configured",
        message: "nope",
      });
    });

    const response = await start(
      new Request("https://app.test/integrations/calendar/microsoft/start"),
      params("microsoft"),
    );

    const target = location(response);
    expect(target.pathname).toBe("/settings");
    expect(target.searchParams.get("calendar_error")).toBe("unavailable");
  });

  it("rejects an unknown provider without calling the service", async () => {
    const response = await start(
      new Request("https://app.test/integrations/calendar/yahoo/start"),
      params("yahoo"),
    );

    expect(post).not.toHaveBeenCalled();
    expect(location(response).searchParams.get("calendar_error")).toBe("authorization_failed");
  });

  it("callback hands the code and state to the service", async () => {
    post.mockResolvedValue({ id: "c1" });

    const response = await callback(
      new Request("https://app.test/integrations/calendar/google/callback?code=abc&state=xyz"),
      params("google"),
    );

    expect(post).toHaveBeenCalledWith(
      "/api/v1/calendar/connections/google/callback",
      { code: "abc", state: "xyz" },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    const target = location(response);
    expect(target.pathname).toBe("/settings");
    expect(target.searchParams.get("calendar")).toBe("connected");
  });

  it("callback explains a declined consent", async () => {
    const response = await callback(
      new Request("https://app.test/integrations/calendar/google/callback?error=access_denied"),
      params("google"),
    );

    expect(post).not.toHaveBeenCalled();
    expect(location(response).searchParams.get("calendar_error")).toBe("access_denied");
  });

  it("callback maps service errors to known notices only", async () => {
    post.mockImplementation(async () => {
      throw new ApiError("validation", 422, { code: "invalid_oauth_state", message: "expired" });
    });
    const expired = await callback(
      new Request("https://app.test/integrations/calendar/google/callback?code=a&state=b"),
      params("google"),
    );
    expect(location(expired).searchParams.get("calendar_error")).toBe("invalid_oauth_state");

    post.mockImplementation(async () => {
      throw new ApiError("validation", 422, { code: "<script>", message: "odd" });
    });
    const odd = await callback(
      new Request("https://app.test/integrations/calendar/google/callback?code=a&state=b"),
      params("google"),
    );
    expect(location(odd).searchParams.get("calendar_error")).toBe("authorization_failed");
  });

  it("never redirects to the server's own address", async () => {
    // The standalone server reports its bind address as the request host.
    post.mockResolvedValue({ id: "c1" });
    const response = await callback(
      new Request("https://localhost:3000/integrations/calendar/google/callback?code=a&state=b"),
      params("google"),
    );

    expect(response.headers.get("location")).toBe("/settings?calendar=connected#calendar");
  });

  it("names a credential rejection instead of calling it an outage", async () => {
    post.mockImplementation(async () => {
      throw new ApiError("validation", 422, {
        code: "calendar_client_rejected",
        message: "rejected",
      });
    });
    const response = await callback(
      new Request("https://app.test/integrations/calendar/google/callback?code=a&state=b"),
      params("google"),
    );
    expect(location(response).searchParams.get("calendar_error")).toBe(
      "calendar_client_rejected",
    );
  });
});
