import { apiClient, ApiError } from "@/lib/server/api-client";
import type { CollectionItem } from "@/types/api";

export const dynamic = "force-dynamic";
const headers = { "Cache-Control": "private, no-store" };

export async function GET(request: Request): Promise<Response> {
  try {
    const items = await apiClient.get<CollectionItem[]>("/api/v1/collection", { signal: AbortSignal.any([request.signal, AbortSignal.timeout(10_000)]) });
    return Response.json(items.filter((item) => item.status === "wishlist").map((item) => item.fragrance.id), { headers });
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 503;
    const message = status === 401 ? "Sign in again to continue." : status === 403 ? "You do not have access to this wishlist." : "Wishlist status is temporarily unavailable.";
    return Response.json({ message }, { status, headers });
  }
}
