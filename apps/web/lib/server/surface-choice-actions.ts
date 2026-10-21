"use server";

import { apiClient, ApiError } from "@/lib/server/api-client";
import type { DiscoveryResult } from "@/types/api";
import type { LayeringStackSuggestion } from "@/types/layering";

export type SurfaceChoice = {
  batch_id: string;
  selected: DiscoveryResult | LayeringStackSuggestion | null;
  candidate_id: string | null;
  remaining_options: number;
  options_exhausted: boolean;
};
export type SurfaceChoiceInput = {
  batch_id?: string;
  idempotency_key: string;
  reset?: boolean;
  advance?: boolean;
  expected_candidate_id?: string | null;
  parameters: Record<string, unknown>;
};

export async function surfaceChoice(
  surface: "discovery" | "layering",
  request: SurfaceChoiceInput,
): Promise<{ ok: true; data: SurfaceChoice } | { ok: false; error: string; code?: string }> {
  try {
    const data = await apiClient.post<SurfaceChoice>(
      `/api/v1/recommendation-options/${surface}`, request, { timeoutMs: 60_000 },
    );
    return { ok: true, data };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof ApiError ? error.message : "Could not load another option. Try again.",
      code: error instanceof ApiError ? error.code : undefined,
    };
  }
}
