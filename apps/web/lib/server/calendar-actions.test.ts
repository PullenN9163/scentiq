import { beforeEach, expect, it, vi } from "vitest";

const { patch, revalidatePath } = vi.hoisted(() => ({ patch: vi.fn(), revalidatePath: vi.fn() }));
vi.mock("@clerk/nextjs/server", () => ({ auth: vi.fn(), clerkClient: vi.fn() }));
vi.mock("next/cache", () => ({ revalidatePath }));
vi.mock("@/lib/server/api-client", () => ({ apiClient: { patch }, ApiError: class extends Error {} }));

import { updateCalendarEvent } from "./actions";

beforeEach(() => vi.clearAllMocks());

function eventForm(occasion = "formal") {
  const data = new FormData();
  data.set("event_id", "9d97bb1e-c50e-41aa-9948-3990c193bc79");
  data.set("occasion", occasion);
  data.set("setting", "outdoor");
  data.set("formality", "");
  return data;
}

it("saves validated corrections with nullable unspecified formality and refreshes plans", async () => {
  const result = await updateCalendarEvent({ status: "idle" }, eventForm());
  expect(result.status).toBe("success");
  expect(patch).toHaveBeenCalledWith("/api/v1/calendar/events/9d97bb1e-c50e-41aa-9948-3990c193bc79", {
    occasion: "formal", setting: "outdoor", formality: null,
  });
  expect(revalidatePath).toHaveBeenCalledWith("/dashboard");
});

it("rejects unsupported corrections before contacting the API", async () => {
  expect((await updateCalendarEvent({ status: "idle" }, eventForm("invented"))).status).toBe("error");
  expect(patch).not.toHaveBeenCalled();
});

it("keeps API failure visible without claiming the correction was saved", async () => {
  patch.mockRejectedValueOnce(new Error("unavailable"));
  expect((await updateCalendarEvent({ status: "idle" }, eventForm())).status).toBe("error");
  expect(revalidatePath).not.toHaveBeenCalled();
});
