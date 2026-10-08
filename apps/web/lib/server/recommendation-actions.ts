"use server";

import { revalidatePath } from "next/cache";
import { apiClient, ApiError } from "@/lib/server/api-client";
import type { DecisionAction, WearRequest } from "@/types/wear-intelligence";
import type { WearLogEntry } from "@/types/api";

type Result<T> = { ok: true; data: T } | { ok: false; error: string };
function refresh() {
  for (const path of ["/dashboard", "/week", "/collection", "/insights", "/agent"]) revalidatePath(path);
}

export async function decideRecommendation(id: string, action: DecisionAction, selectedFragranceId?: string): Promise<Result<unknown>> {
  try {
    const data = await apiClient.post(`/api/v1/recommendations/${encodeURIComponent(id)}/decision`, { action, selected_fragrance_id: selectedFragranceId ?? null });
    refresh();
    return { ok: true, data };
  } catch (error) {
    return { ok: false, error: error instanceof ApiError ? error.message : "Could not save that choice. Try again." };
  }
}

export async function wearRecommendation(id: string, payload: WearRequest): Promise<Result<WearLogEntry>> {
  try {
    const data = await apiClient.post<WearLogEntry>(`/api/v1/recommendations/${encodeURIComponent(id)}/wear`, payload);
    refresh();
    return { ok: true, data };
  } catch (error) {
    return { ok: false, error: error instanceof ApiError ? error.message : "Could not log this wear. Try again." };
  }
}
