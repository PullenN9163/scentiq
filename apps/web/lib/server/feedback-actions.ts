"use server";
import { auth } from "@clerk/nextjs/server";
import { revalidatePath } from "next/cache";
import { z } from "zod";
import type { ActionState } from "@/lib/action-state";
import { apiClient } from "./api-client";

export async function getWearFeedback(id: string): Promise<{ rating: number | null; longevity: number | null; projection: "intimate" | "moderate" | "strong" | null; comments: string | null } | null> {
  if (!z.uuid().safeParse(id).success) return null;
  return apiClient.get(`/api/v1/wear-logs/${id}/feedback`);
}
export async function saveWearFeedback(_: ActionState, form: FormData): Promise<ActionState> {
  const fields = ["wear_log_id", "rating", "longevity", "projection", "comments"];
  const values = Object.fromEntries(fields.map((key) => [key, String(form.get(key) ?? "")]));
  const optionalNumber = (max: number) => z.string().transform((value) => value.trim() === "" ? null : Number(value)).pipe(z.number().min(0).max(max).nullable());
  const parsed = z.object({ wear_log_id: z.uuid(), rating: z.string().transform((value) => value === "" ? null : Number(value)).pipe(z.number().int().min(1).max(5).nullable()), longevity: optionalNumber(10), projection: z.union([z.literal(""), z.enum(["intimate", "moderate", "strong"])]).transform((value) => value || null), comments: z.string().max(2000).transform((value) => value.trim() || null) }).safeParse(values);
  if (!parsed.success) return { status: "error", message: "Check your feedback values.", values, fieldErrors: Object.fromEntries(parsed.error.issues.map((issue) => [issue.path.join("."), issue.message])) };
  const { wear_log_id, ...body } = parsed.data;
  const token = await (await auth()).getToken();
  if (!token) return { status: "error", message: "Sign in to continue.", values };
  const base = process.env.API_INTERNAL_URL || (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");
  if (!base) return { status: "error", message: "ScentIQ is unavailable.", values };
  try {
    const response = await fetch(`${base.replace(/\/+$/, "")}/api/v1/wear-logs/${wear_log_id}/feedback`, { method: "PUT", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }, body: JSON.stringify(body), cache: "no-store", signal: AbortSignal.timeout(10_000) });
    if (!response.ok) return { status: "error", message: "Feedback could not be saved. Try again.", values };
    revalidatePath("/collection"); revalidatePath("/insights"); revalidatePath("/dashboard"); revalidatePath("/week");
    return { status: "success", message: "Feedback saved." };
  } catch { return { status: "error", message: "Feedback could not be saved. Try again.", values }; }
}
