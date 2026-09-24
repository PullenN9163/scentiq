import "server-only";

import { auth } from "@clerk/nextjs/server";

/**
 * The single server-only route to FastAPI.
 *
 * The browser never reaches FastAPI: it talks to Next.js, which attaches the
 * Clerk session token and calls the service over `API_INTERNAL_URL`. Importing
 * this module from a Client Component is a build error, which is what keeps the
 * token on the server.
 */

export type ApiFieldError = {
  field: string;
  code: string;
  message: string;
};

export type ApiErrorBody = {
  code: string;
  message: string;
  field_errors?: ApiFieldError[];
  request_id?: string;
};

/** Why a call failed, in terms the UI can branch on. */
export type ApiFailureKind =
  | "unauthorized"
  | "forbidden"
  | "not_found"
  | "conflict"
  | "validation"
  | "unavailable"
  | "unknown";

export class ApiError extends Error {
  readonly kind: ApiFailureKind;
  readonly status: number;
  readonly code: string;
  readonly fieldErrors: ApiFieldError[];
  readonly requestId?: string;

  constructor(kind: ApiFailureKind, status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
    this.code = body.code;
    this.fieldErrors = body.field_errors ?? [];
    this.requestId = body.request_id;
  }

  /** Field errors keyed by field name, for rendering beside inputs. */
  fieldErrorMap(): Record<string, string> {
    const map: Record<string, string> = {};
    for (const error of this.fieldErrors) {
      map[error.field] ??= error.message;
    }
    return map;
  }
}

function kindFor(status: number): ApiFailureKind {
  if (status === 401) return "unauthorized";
  if (status === 403) return "forbidden";
  if (status === 404) return "not_found";
  if (status === 409) return "conflict";
  if (status === 422 || status === 400) return "validation";
  if (status === 502 || status === 503 || status === 504) return "unavailable";
  return "unknown";
}

function internalBaseUrl(): string {
  const developmentDefault =
    process.env.NODE_ENV === "development" ? "http://localhost:8000" : undefined;
  const baseUrl = process.env.API_INTERNAL_URL || developmentDefault;
  if (!baseUrl) {
    throw new ApiError("unavailable", 503, {
      code: "api_not_configured",
      message: "The ScentIQ service address is not configured.",
    });
  }
  return baseUrl.replace(/\/+$/, "");
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH";
  body?: unknown;
  signal?: AbortSignal;
};

async function readErrorBody(response: Response): Promise<ApiErrorBody> {
  try {
    const parsed = (await response.json()) as unknown;
    if (parsed && typeof parsed === "object" && "code" in parsed && "message" in parsed) {
      return parsed as ApiErrorBody;
    }
  } catch {
    // Fall through to a generic body below.
  }
  return {
    code: response.status === 503 ? "service_unavailable" : "error",
    message: "The ScentIQ service could not complete that request.",
  };
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, signal } = options;

  const { getToken } = await auth();
  const token = await getToken();
  if (!token) {
    throw new ApiError("unauthorized", 401, {
      code: "unauthorized",
      message: "Your session has expired. Sign in again to continue.",
    });
  }

  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  let response: Response;
  try {
    response = await fetch(`${internalBaseUrl()}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: signal ?? AbortSignal.timeout(10_000),
      // Never cached. These responses are per-member and carry a bearer token,
      // so caching them risks serving one member's data to another. Server
      // Actions revalidate by path instead, which re-runs the read.
      cache: "no-store",
    });
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError("unavailable", 503, {
      code: "service_unreachable",
      message: "ScentIQ could not reach the service. Try again in a moment.",
    });
  }

  if (response.status === 204) {
    return undefined as T;
  }

  if (!response.ok) {
    throw new ApiError(kindFor(response.status), response.status, await readErrorBody(response));
  }

  return (await response.json()) as T;
}

export const apiClient = {
  get: <T>(path: string, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "POST", body }),
  patch: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "PATCH", body }),
};
