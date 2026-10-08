"use server";

import { revalidatePath } from "next/cache";
import { z } from "zod";
import { apiClient } from "@/lib/server/api-client";
import type { DiscoveryResult } from "@/types/api";
import type {
  LayeringGoal,
  LayeringIntelligencePage,
  LayeringStackSuggestion,
  LayeringStackWear,
  SavedLayeringStack,
  StackMode,
} from "@/types/layering";

const modeSchema = z.enum(["safe", "balanced", "contrast", "experimental"]);
const goalSchema = z.enum([
  "fresher",
  "warmer",
  "sweeter",
  "darker",
  "cleaner",
  "softer",
  "more_projection",
  "more_intimate",
  "daytime",
  "evening",
  "spring",
  "summer",
  "fall",
  "winter",
]);
const stackSchema = z.object({
  fragrance_ids: z
    .array(z.uuid())
    .min(2)
    .max(3)
    .refine((ids) => new Set(ids).size === ids.length),
  mode: modeSchema,
  goal: goalSchema.nullable(),
});
function refresh() {
  ["/layering", "/insights", "/dashboard", "/week", "/collection"].forEach(
    (path) => revalidatePath(path),
  );
}

export async function getLayeringIntelligence(
  options: {
    anchorId?: string;
    mode?: StackMode;
    goal?: LayeringGoal | null;
  } = {},
): Promise<LayeringIntelligencePage> {
  const parameters = new URLSearchParams();
  if (options.anchorId)
    parameters.set("anchor_id", z.uuid().parse(options.anchorId));
  parameters.set("mode", modeSchema.parse(options.mode ?? "balanced"));
  if (options.goal) parameters.set("goal", goalSchema.parse(options.goal));
  return apiClient.get<LayeringIntelligencePage>(
    `/api/v1/layering/intelligence?${parameters}`,
  );
}
export async function evaluateLayerStack(
  ids: string[],
  mode: StackMode,
  goal: LayeringGoal | null,
): Promise<LayeringStackSuggestion> {
  return apiClient.post<LayeringStackSuggestion>(
    "/api/v1/layering/stacks/evaluate",
    stackSchema.parse({ fragrance_ids: ids, mode, goal }),
  );
}
export async function saveLayerStack(
  ids: string[],
  mode: StackMode,
  goal: LayeringGoal | null,
  name: string,
  notes?: string,
): Promise<SavedLayeringStack> {
  const body = {
    ...stackSchema.parse({ fragrance_ids: ids, mode, goal }),
    name: z.string().trim().min(1).max(120).parse(name),
    notes: z.string().max(2000).optional().parse(notes),
  };
  const saved = await apiClient.post<SavedLayeringStack>(
    "/api/v1/layering/stacks",
    body,
  );
  refresh();
  return saved;
}
export async function renameLayerStack(
  id: string,
  name: string,
): Promise<SavedLayeringStack> {
  const saved = await apiClient.patch<SavedLayeringStack>(
    `/api/v1/layering/stacks/${z.uuid().parse(id)}`,
    { name: z.string().trim().min(1).max(120).parse(name) },
  );
  refresh();
  return saved;
}
export async function deleteLayerStack(id: string): Promise<void> {
  await apiClient.delete(`/api/v1/layering/stacks/${z.uuid().parse(id)}`);
  refresh();
}
export async function logLayerStackWear(
  id: string,
  rating: number | null,
  notes: string,
): Promise<LayeringStackWear> {
  const wear = await apiClient.post<LayeringStackWear>(
    `/api/v1/layering/stacks/${z.uuid().parse(id)}/wears`,
    {
      rating: z.number().int().min(1).max(5).nullable().parse(rating),
      notes: z.string().max(2000).parse(notes) || null,
    },
  );
  refresh();
  return wear;
}
export async function getLayerStackHistory(
  id: string,
): Promise<LayeringStackWear[]> {
  return apiClient.get<LayeringStackWear[]>(
    `/api/v1/layering/stacks/${z.uuid().parse(id)}/wears`,
  );
}
export async function rateLayerStackWear(
  stackId: string,
  wearId: string,
  rating: number,
): Promise<LayeringStackWear> {
  const wear = await apiClient.patch<LayeringStackWear>(
    `/api/v1/layering/stacks/${z.uuid().parse(stackId)}/wears/${z.uuid().parse(wearId)}/rating`,
    { rating: z.number().int().min(1).max(5).parse(rating) },
  );
  refresh();
  return wear;
}
export async function getDiscoveryIntelligence(
  options: {
    mode?: string;
    gender?: string;
    family?: string;
    season?: string;
    minimumValue?: string;
  } = {},
): Promise<DiscoveryResult[]> {
  const parameters = new URLSearchParams();
  parameters.set(
    "mode",
    z
      .enum(["balance", "taste", "explore", "seasonal"])
      .parse(options.mode ?? "balance"),
  );
  if (options.gender) parameters.set("gender", options.gender);
  if (options.family) parameters.set("family", options.family);
  if (options.season) parameters.set("season", options.season);
  if (options.minimumValue)
    parameters.set("minimum_value", options.minimumValue);
  return apiClient.get<DiscoveryResult[]>(`/api/v1/discover?${parameters}`);
}
