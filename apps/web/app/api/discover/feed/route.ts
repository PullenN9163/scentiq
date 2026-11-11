import { apiClient, ApiError } from "@/lib/server/api-client";
import type { DiscoveryResult } from "@/types/api";

export const dynamic = "force-dynamic";
const headers = { "Cache-Control": "private, no-store" };
const modes = ["balance", "taste", "explore", "seasonal"] as const;

export async function GET(request: Request): Promise<Response> {
  const params = new URL(request.url).searchParams;
  const mode = modes.includes(params.get("mode") as typeof modes[number]) ? params.get("mode")! : "balance";
  const limitInput = Number(params.get("limit") ?? 25);
  const offsetInput = Number(params.get("offset") ?? 0);
  if (!Number.isInteger(limitInput) || !Number.isInteger(offsetInput) || offsetInput < 0 || offsetInput > 10_000) {
    return Response.json({ message: "Check your discovery filters." }, { status: 400, headers });
  }
  const query = new URLSearchParams({ mode, limit: String(Math.min(Math.max(limitInput, 1), 50)), offset: String(offsetInput) });
  const family=params.get("family")?.trim();
  const gender=params.get("gender");
  const season=params.get("season");
  const minimumValue=params.get("minimum_value");
  if (family && family.length>60) return Response.json({message:"Check your discovery filters."},{status:400,headers});
  if (gender && !["male","female","unisex"].includes(gender)) return Response.json({message:"Check your discovery filters."},{status:400,headers});
  if (season && !["spring","summer","fall","winter"].includes(season)) return Response.json({message:"Check your discovery filters."},{status:400,headers});
  if (minimumValue && (!Number.isFinite(Number(minimumValue)) || Number(minimumValue)<1 || Number(minimumValue)>5)) return Response.json({message:"Check your discovery filters."},{status:400,headers});
  if (family) query.set("family",family);
  if (gender) query.set("gender",gender);
  if (season) query.set("season",season);
  if (minimumValue) query.set("minimum_value",minimumValue);
  try {
    const data = await apiClient.get<{items: DiscoveryResult[]; mode: string; limit: number; offset: number; generated_at: string | null; refresh_status: "fresh" | "pending" | "fallback"}>(`/api/v1/discovery-feed?${query}`, { signal: AbortSignal.any([request.signal, AbortSignal.timeout(10_000)]) });
    return Response.json(data, { headers });
  } catch (error) {
    const status = error instanceof ApiError ? error.status : 503;
    const message = status === 401 ? "Sign in again to continue." : status === 403 ? "You do not have access to recommendations." : "Recommendations are temporarily unavailable. Try again.";
    return Response.json({ message }, { status, headers });
  }
}
