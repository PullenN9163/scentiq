"use server";

import { auth, clerkClient } from "@clerk/nextjs/server";
import { revalidatePath } from "next/cache";
import { z } from "zod";

import type { ActionState } from "@/lib/action-state";
import { ApiError, apiClient } from "@/lib/server/api-client";

/**
 * Refreshes the screens a collection or wear change affects.
 *
 * Reads are never cached, so this exists to make the router re-render the
 * affected routes rather than to clear a cache entry.
 */
function refreshCollectionScreens(): void {
  revalidatePath("/collection");
  revalidatePath("/insights");
  revalidatePath("/dashboard");
}

/** Refreshes the screens a profile or preference change affects. */
function refreshMemberScreens(): void {
  revalidatePath("/settings");
  revalidatePath("/dashboard");
}

function textOf(formData: FormData, field: string): string {
  const value = formData.get(field);
  return typeof value === "string" ? value : "";
}

/** Collects the submitted values so the form can be re-rendered unchanged. */
function echo(formData: FormData, fields: string[]): Record<string, string> {
  const values: Record<string, string> = {};
  for (const field of fields) {
    values[field] = textOf(formData, field);
  }
  return values;
}

function failureFrom(error: unknown, values: Record<string, string>): ActionState {
  if (error instanceof ApiError) {
    return {
      status: "error",
      message: error.message,
      fieldErrors: error.fieldErrors.length > 0 ? error.fieldErrorMap() : undefined,
      values,
    };
  }
  return {
    status: "error",
    message: "Something went wrong. Please try again.",
    values,
  };
}

function zodFieldErrors(error: z.ZodError): Record<string, string> {
  const fieldErrors: Record<string, string> = {};
  for (const issue of error.issues) {
    const field = issue.path.join(".") || "form";
    fieldErrors[field] ??= issue.message;
  }
  return fieldErrors;
}

/** Empty string means "not provided", which the API expects as null. */
const optionalText = z
  .string()
  .trim()
  .transform((value) => (value === "" ? null : value));

const optionalNumber = z
  .string()
  .trim()
  .transform((value) => (value === "" ? null : Number(value)))
  .refine((value) => value === null || Number.isFinite(value), "Enter a number");

// --- profile and preferences -------------------------------------------

const profileSchema = z.object({
  display_name: z.string().trim().min(1, "Enter a display name").max(120),
});

export async function updateProfile(
  _previous: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const values = echo(formData, ["display_name"]);
  const parsed = profileSchema.safeParse({ display_name: textOf(formData, "display_name") });
  if (!parsed.success) {
    return { status: "error", fieldErrors: zodFieldErrors(parsed.error), values };
  }

  try {
    await apiClient.patch("/api/v1/me", parsed.data);
  } catch (error) {
    return failureFrom(error, values);
  }

  refreshMemberScreens();
  return { status: "success", message: "Profile updated." };
}

const preferencesSchema = z.object({
  location: optionalText,
  preferred_season: z.enum(["spring", "summer", "fall", "winter"]).nullable(),
  preferred_occasion: z
    .enum(["work", "casual", "date", "dinner", "party", "formal", "gym", "travel", "other"])
    .nullable(),
  preferred_projection: z.enum(["intimate", "moderate", "strong"]).nullable(),
  preferred_longevity: optionalNumber,
  maximum_sprays: optionalNumber,
});

function nullableEnum(formData: FormData, field: string): string | null {
  const value = textOf(formData, field).trim();
  return value === "" ? null : value;
}

export async function updatePreferences(
  _previous: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const fields = [
    "location",
    "preferred_season",
    "preferred_occasion",
    "preferred_projection",
    "preferred_longevity",
    "maximum_sprays",
  ];
  const values = echo(formData, fields);

  const parsed = preferencesSchema.safeParse({
    location: textOf(formData, "location"),
    preferred_season: nullableEnum(formData, "preferred_season"),
    preferred_occasion: nullableEnum(formData, "preferred_occasion"),
    preferred_projection: nullableEnum(formData, "preferred_projection"),
    preferred_longevity: textOf(formData, "preferred_longevity"),
    maximum_sprays: textOf(formData, "maximum_sprays"),
  });
  if (!parsed.success) {
    return { status: "error", fieldErrors: zodFieldErrors(parsed.error), values };
  }

  try {
    await apiClient.patch("/api/v1/me/preferences", parsed.data);
  } catch (error) {
    return failureFrom(error, values);
  }

  refreshMemberScreens();
  return { status: "success", message: "Preferences saved." };
}

// --- custom fragrances -------------------------------------------------

const customFragranceSchema = z.object({
  brand_name: z.string().trim().min(1, "Enter a brand").max(120),
  name: z.string().trim().min(1, "Enter a fragrance name").max(160),
  concentration: z.string().trim().min(1, "Enter a concentration").max(40),
  release_year: optionalNumber,
  description: optionalText,
  projection_level: z.enum(["intimate", "moderate", "strong"]).nullable(),
});

export async function createCustomFragrance(
  _previous: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const fields = [
    "brand_name",
    "name",
    "concentration",
    "release_year",
    "description",
    "projection_level",
  ];
  const values = echo(formData, fields);

  const parsed = customFragranceSchema.safeParse({
    brand_name: textOf(formData, "brand_name"),
    name: textOf(formData, "name"),
    concentration: textOf(formData, "concentration"),
    release_year: textOf(formData, "release_year"),
    description: textOf(formData, "description"),
    projection_level: nullableEnum(formData, "projection_level"),
  });
  if (!parsed.success) {
    return { status: "error", fieldErrors: zodFieldErrors(parsed.error), values };
  }

  try {
    await apiClient.post("/api/v1/fragrances", parsed.data);
  } catch (error) {
    return failureFrom(error, values);
  }

  refreshCollectionScreens();
  return { status: "success", message: "Custom fragrance added." };
}

// --- collection --------------------------------------------------------

const addToCollectionSchema = z.object({
  fragrance_id: z.string().uuid("Choose a fragrance"),
  ownership_type: z.enum(["bottle", "decant", "sample"]),
  status: z.enum(["owned", "wishlist", "finished", "sold"]),
  bottle_size_ml: optionalNumber,
  remaining_ml: optionalNumber,
  purchase_price: optionalText,
  purchase_date: optionalText,
  user_rating: optionalNumber,
});

export async function addToCollection(
  _previous: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const fields = [
    "fragrance_id",
    "ownership_type",
    "status",
    "bottle_size_ml",
    "remaining_ml",
    "purchase_price",
    "purchase_date",
    "user_rating",
  ];
  const values = echo(formData, fields);

  const parsed = addToCollectionSchema.safeParse({
    fragrance_id: textOf(formData, "fragrance_id"),
    ownership_type: textOf(formData, "ownership_type") || "bottle",
    status: textOf(formData, "status") || "owned",
    bottle_size_ml: textOf(formData, "bottle_size_ml"),
    remaining_ml: textOf(formData, "remaining_ml"),
    purchase_price: textOf(formData, "purchase_price"),
    purchase_date: textOf(formData, "purchase_date"),
    user_rating: textOf(formData, "user_rating"),
  });
  if (!parsed.success) {
    return { status: "error", fieldErrors: zodFieldErrors(parsed.error), values };
  }

  try {
    await apiClient.post("/api/v1/collection", parsed.data);
  } catch (error) {
    return failureFrom(error, values);
  }

  refreshCollectionScreens();
  return { status: "success", message: "Added to your collection." };
}

const updateCollectionSchema = z.object({
  ownership_type: z.enum(["bottle", "decant", "sample"]).optional(),
  status: z.enum(["owned", "wishlist", "finished", "sold"]).optional(),
  remaining_ml: optionalNumber,
  purchase_price: optionalText,
  user_rating: optionalNumber,
});

export async function updateCollectionItem(
  _previous: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const itemId = textOf(formData, "item_id");
  const fields = ["ownership_type", "status", "remaining_ml", "purchase_price", "user_rating"];
  const values = echo(formData, fields);

  if (!itemId) {
    return { status: "error", message: "That collection item could not be identified.", values };
  }

  const submitted: Record<string, unknown> = {};
  const ownership = textOf(formData, "ownership_type").trim();
  const status = textOf(formData, "status").trim();
  if (ownership) submitted.ownership_type = ownership;
  if (status) submitted.status = status;
  submitted.remaining_ml = textOf(formData, "remaining_ml");
  submitted.purchase_price = textOf(formData, "purchase_price");
  submitted.user_rating = textOf(formData, "user_rating");

  const parsed = updateCollectionSchema.safeParse(submitted);
  if (!parsed.success) {
    return { status: "error", fieldErrors: zodFieldErrors(parsed.error), values };
  }

  try {
    await apiClient.patch(`/api/v1/collection/${itemId}`, parsed.data);
  } catch (error) {
    return failureFrom(error, values);
  }

  refreshCollectionScreens();
  return { status: "success", message: "Collection item updated." };
}

// --- wear logging ------------------------------------------------------

const wearLogSchema = z.object({
  collection_item_id: z.string().uuid("Choose an item from your collection"),
  worn_at: z.string().min(1, "Choose when you wore it"),
  sprays: optionalNumber,
  occasion: z
    .enum(["work", "casual", "date", "dinner", "party", "formal", "gym", "travel", "other"])
    .nullable(),
  setting: optionalText,
  notes: optionalText,
});

export async function logWear(_previous: ActionState, formData: FormData): Promise<ActionState> {
  const fields = ["collection_item_id", "worn_at", "sprays", "occasion", "setting", "notes"];
  const values = echo(formData, fields);

  const submittedWornAt = textOf(formData, "worn_at").trim();
  // A datetime-local input has no offset; treat it as the browser's moment by
  // letting the Date constructor apply the server's interpretation, then send
  // an explicit UTC instant, which the API requires.
  const wornAtIso = submittedWornAt ? new Date(submittedWornAt).toISOString() : "";

  const parsed = wearLogSchema.safeParse({
    collection_item_id: textOf(formData, "collection_item_id"),
    worn_at: wornAtIso,
    sprays: textOf(formData, "sprays"),
    occasion: nullableEnum(formData, "occasion"),
    setting: textOf(formData, "setting"),
    notes: textOf(formData, "notes"),
  });
  if (!parsed.success) {
    return { status: "error", fieldErrors: zodFieldErrors(parsed.error), values };
  }

  try {
    await apiClient.post("/api/v1/wear-logs", parsed.data);
  } catch (error) {
    return failureFrom(error, values);
  }

  refreshCollectionScreens();
  return { status: "success", message: "Wear logged." };
}

// --- account deletion --------------------------------------------------

/**
 * Phase one of deletion.
 *
 * ScentIQ is marked pending first, then the Clerk identity is deleted. If Clerk
 * refuses, the pending mark is rolled back so the account stays usable rather
 * than being stranded. The signed `user.deleted` webhook removes the data.
 */
export async function deleteAccount(
  _previous: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const confirmation = textOf(formData, "confirmation").trim();
  if (confirmation.toLowerCase() !== "delete") {
    return {
      status: "error",
      fieldErrors: { confirmation: 'Type "delete" to confirm' },
      values: { confirmation },
    };
  }

  const { userId } = await auth();
  if (!userId) {
    return { status: "error", message: "Your session has expired. Sign in again to continue." };
  }

  try {
    await apiClient.post("/api/v1/me/deletion");
  } catch (error) {
    return failureFrom(error, { confirmation });
  }

  try {
    const clerk = await clerkClient();
    await clerk.users.deleteUser(userId);
  } catch {
    // Roll the pending mark back; without this the account would be unusable
    // but never actually deleted.
    try {
      await apiClient.post("/api/v1/me/deletion/cancel");
    } catch {
      // Reconciliation will pick this up if the rollback itself fails.
    }
    refreshMemberScreens();
    return {
      status: "error",
      message: "We could not complete the deletion. Nothing was removed — please try again.",
      values: { confirmation },
    };
  }

  refreshMemberScreens();
  return { status: "success", message: "Your account is being deleted." };
}
