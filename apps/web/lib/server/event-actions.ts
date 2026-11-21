"use server";

import { z } from "zod";
import { apiClient } from "@/lib/server/api-client";

const eventSchema = z.object({
  event_type: z.enum([
    "view",
    "accept",
    "reject",
    "skip",
    "dismiss",
    "wear",
    "like",
    "dislike",
    "surprise_click",
    "surprise_shown",
    "filter_select",
    "stack_save",
    "stack_edit",
    "stack_discard",
    "stack_wear",
  ]),
  subject_type: z.enum(["fragrance", "stack", "recommendation", "ui"]).default("fragrance"),
  fragrance_ids: z.array(z.uuid()).max(3).default([]),
  rating: z.number().int().min(1).max(5).nullable().optional(),
  context: z.record(z.string().max(30), z.string().max(40)).default({}),
});
export type InteractionEvent = z.input<typeof eventSchema>;

/** Fire-and-forget learning signal. A failed event must never block the interface. */
export async function recordEvents(events: InteractionEvent[]): Promise<void> {
  const parsed = z.array(eventSchema).min(1).max(50).safeParse(events);
  if (!parsed.success) return;
  try {
    await apiClient.post("/api/v1/events", {
      events: parsed.data.map((event) => ({ ...event, rating: event.rating ?? null })),
    });
  } catch {
    // Learning is best-effort by design.
  }
}
