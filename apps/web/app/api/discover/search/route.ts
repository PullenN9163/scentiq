import { apiClient, ApiError } from "@/lib/server/api-client";
import type { FragranceSummary } from "@/types/api";

export const dynamic = "force-dynamic";
const headers = { "Cache-Control": "private, no-store" };

export async function GET(request: Request): Promise<Response> {
  const params = new URL(request.url).searchParams;
  const query = (params.get("q") ?? "").trim().slice(0, 120);
  const rawLimit = Number(params.get("limit") ?? 25);
  const rawOffset = Number(params.get("offset") ?? 0);
  if (!query || !Number.isInteger(rawLimit) || !Number.isInteger(rawOffset) || rawOffset < 0 || rawOffset > 10_000) {
    return Response.json({ message: "Enter a search term." }, { status: 400, headers });
  }
  const limit = Math.min(Math.max(rawLimit, 1), 50);
  const upstream = new URLSearchParams({ q: query, limit: String(limit), offset: String(rawOffset), sort: "relevance" });
  const family=params.get("family")?.trim();
  const gender=params.get("gender");
  const season=params.get("season");
  const minimumValue=params.get("minimum_value");
  if (family && family.length>60) return Response.json({message:"Check your search filters."},{status:400,headers});
  if (gender && !["male","female","unisex"].includes(gender)) return Response.json({message:"Check your search filters."},{status:400,headers});
  if (season && !["spring","summer","fall","winter"].includes(season)) return Response.json({message:"Check your search filters."},{status:400,headers});
  if (minimumValue && (!Number.isFinite(Number(minimumValue)) || Number(minimumValue)<1 || Number(minimumValue)>5)) return Response.json({message:"Check your search filters."},{status:400,headers});
  if (family) upstream.set("family",family);
  if (gender) upstream.set("gender",gender);
  if (season) upstream.set("season",season);
  if (minimumValue) upstream.set("minimum_value",minimumValue);
  try {
    const data = await apiClient.get<FragranceSummary[]>(`/api/v1/fragrances?${upstream}`, { signal: AbortSignal.any([request.signal, AbortSignal.timeout(10_000)]) });
    return Response.json(data, { headers });
  } catch (error) {
    return apiFailure(error);
  }
}

function apiFailure(error: unknown): Response {
  const status = error instanceof ApiError ? error.status : 503;
  const message = status === 401 ? "Sign in again to continue." : status === 403 ? "You do not have access to these fragrances." : status === 400 || status === 422 ? "Check your search filters." : "Search is temporarily unavailable. Try again.";
  return Response.json({ message }, { status, headers });
}
