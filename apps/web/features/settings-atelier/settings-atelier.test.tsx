import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ChipPicker } from "@/components/atelier/chip-picker";
import { ThemeProvider } from "@/components/ui/theme-provider";
import { readReduceEffects, setReduceEffects } from "@/lib/effects";
import type { Me } from "@/types/api";

import { preferenceValues } from "./preference-values";
import { SettingsAtelier } from "./settings-atelier";
import { sectionFrom } from "./sections";

const server = vi.hoisted(() => ({
  updateProfile: vi.fn(),
  updatePreferences: vi.fn(),
  deleteAccount: vi.fn(),
  setCalendarSelected: vi.fn(),
  syncCalendarConnection: vi.fn(),
  disconnectCalendar: vi.fn(),
}));
vi.mock("@/lib/server/actions", () => server);
const router = vi.hoisted(() => ({ refresh: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const me: Me = {
  id: "m", email: "maya@example.test", display_name: "Maya", lifecycle_state: "active", created_at: "2026-01-01T00:00:00Z",
  preferences: {
    liked_notes: ["Cedar", "Smoked birch"], disliked_notes: ["Oud"], liked_accords: ["Woody"], disliked_accords: [], liked_families: ["Fresh"], disliked_families: ["Gourmand"],
    excluded_fragrance_ids: ["11111111-1111-4111-8111-111111111111"], variety_preference: "adventurous", calendar_ai_titles_enabled: true,
    location: "Leeds, UK", location_label: "Leeds, England", timezone: "Europe/London", temperature_unit: "celsius",
    preferred_season: "fall", preferred_occasion: "work", preferred_projection: "moderate", preferred_longevity: 7.5, maximum_sprays: 4,
  },
};

/** What the existing SettingsView preferences form posts for `me` when nothing is changed. */
const OLD_FORM = {
  liked_notes: "Cedar, Smoked birch", disliked_notes: "Oud", liked_accords: "Woody", disliked_accords: "", liked_families: "Fresh", disliked_families: "Gourmand",
  variety_preference: "adventurous", excluded_fragrance_ids: "11111111-1111-4111-8111-111111111111", calendar_ai_titles_enabled: "on",
  location: "Leeds, UK", temperature_unit: "celsius", preferred_season: "fall", preferred_occasion: "work", preferred_projection: "moderate", preferred_longevity: "7.5", maximum_sprays: "4",
};

beforeEach(() => {
  server.updateProfile.mockResolvedValue({ status: "success", message: "Profile updated." });
  server.updatePreferences.mockResolvedValue({ status: "success", message: "Preferences saved." });
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: false, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  window.history.replaceState({}, "", "/settings");
});
afterEach(() => { vi.clearAllMocks(); vi.unstubAllGlobals(); setReduceEffects(false); });

function renderSettings(section: Parameters<typeof SettingsAtelier>[0]["initialSection"] = null) {
  if (section) window.history.replaceState({}, "", `/settings?section=${section}`);
  return render(<ThemeProvider><SettingsAtelier me={me} calendarProviders={[]} calendarConnections={[]} initialSection={section} /></ThemeProvider>);
}

function posted(): Record<string, string> {
  return Object.fromEntries(server.updatePreferences.mock.calls.at(-1)![1] as FormData) as Record<string, string>;
}

describe("deep links", () => {
  it("reads ?section= first, then the hash", () => {
    expect(sectionFrom("?section=taste", "#calendar")).toBe("taste");
    expect(sectionFrom("", "#calendar")).toBe("calendar");
    expect(sectionFrom("?section=nope", "")).toBeNull();
  });

  it("opens Calendars from /settings#calendar", async () => {
    window.history.replaceState({}, "", "/settings#calendar");
    renderSettings();
    expect(await screen.findByRole("heading", { name: "Calendars" })).toBeInTheDocument();
  });

  it("opens a section from the list and writes it to the address", async () => {
    const user = userEvent.setup();
    renderSettings();
    await user.click(screen.getByRole("button", { name: "Place and weather" }));
    expect(screen.getByRole("heading", { name: "Place and weather" })).toBeInTheDocument();
    expect(window.location.search).toBe("?section=place");
    expect(window.location.hash).toBe("#place");
  });
});

describe("save payloads", () => {
  it("formats saved preferences as the old form did", () => {
    const values = preferenceValues(me.preferences);
    expect(Object.fromEntries(Object.entries(values).filter(([, value]) => value !== null))).toEqual(OLD_FORM);
  });

  it("saves the profile with display_name", async () => {
    const user = userEvent.setup();
    renderSettings("profile");
    const name = screen.getByLabelText("Display name");
    await user.clear(name);
    await user.type(name, "Maya B");
    await user.click(screen.getByRole("button", { name: "Save profile" }));
    await waitFor(() => expect(server.updateProfile).toHaveBeenCalled());
    expect(Object.fromEntries(server.updateProfile.mock.calls[0][1] as FormData)).toEqual({ display_name: "Maya B" });
    expect(await screen.findByText("Saved just now")).toBeInTheDocument();
  });

  it.each(["taste", "place"] as const)("saves %s with every preference field the old form posted", async (section) => {
    const user = userEvent.setup();
    renderSettings(section);
    await user.click(screen.getByRole("button", { name: section === "taste" ? "Save taste" : "Save place" }));
    await waitFor(() => expect(server.updatePreferences).toHaveBeenCalled());
    expect(posted()).toEqual(OLD_FORM);
  });

  it("changes only what the member changed", async () => {
    const user = userEvent.setup();
    renderSettings("taste");
    const liked = screen.getByRole("group", { name: "Liked notes" });
    await user.click(within(liked).getByRole("button", { name: "Vanilla" }));
    await user.click(within(liked).getByRole("button", { name: "Cedar" }));
    await user.click(screen.getByRole("button", { name: "Familiar" }));
    await user.click(screen.getByRole("button", { name: "More maximum sprays" }));
    await user.click(screen.getByRole("button", { name: "Save taste" }));
    await waitFor(() => expect(server.updatePreferences).toHaveBeenCalled());
    expect(posted()).toEqual({ ...OLD_FORM, liked_notes: "Smoked birch, Vanilla", variety_preference: "familiar", maximum_sprays: "5" });
  });

  it("toggles calendar AI titles with the other fields kept", async () => {
    const user = userEvent.setup();
    renderSettings("calendar");
    await user.click(screen.getByRole("switch", { name: "Interpret event titles" }));
    await waitFor(() => expect(server.updatePreferences).toHaveBeenCalled());
    const { calendar_ai_titles_enabled: _removed, ...rest } = OLD_FORM;
    void _removed;
    expect(posted()).toEqual(rest);
  });

  it("shows a section error under its button and keeps values", async () => {
    const user = userEvent.setup();
    server.updatePreferences.mockResolvedValueOnce({ status: "error", message: "Check the highlighted fields.", values: { ...OLD_FORM, location: "Nowhere" }, fieldErrors: { location: "We could not find that place." } });
    renderSettings("place");
    const location = screen.getByLabelText("Location");
    await user.clear(location);
    await user.type(location, "Nowhere");
    await user.click(screen.getByRole("button", { name: "Save place" }));
    expect(await screen.findByText("We could not find that place.")).toBeInTheDocument();
    expect(screen.getByLabelText("Location")).toHaveValue("Nowhere");
  });
});

describe("chip picker", () => {
  it("round-trips comma-separated values, including unknown and added ones", async () => {
    const user = userEvent.setup();
    const { container } = render(<form><ChipPicker name="liked_notes" label="Liked notes" choices={["Cedar", "Rose"]} defaultValue={["Cedar", "Smoked birch"]} /></form>);
    const hidden = container.querySelector("input[name='liked_notes']") as HTMLInputElement;
    expect(hidden.value).toBe("Cedar, Smoked birch");
    expect(screen.getByRole("button", { name: "Smoked birch" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "Rose" }));
    await user.click(screen.getByRole("button", { name: "Add to liked notes" }));
    await user.type(screen.getByLabelText("Add to liked notes"), "Fig leaf{Enter}");
    expect(hidden.value).toBe("Cedar, Smoked birch, Rose, Fig leaf");
  });
});

describe("appearance", () => {
  it("writes the reduce effects cookie and root attribute", async () => {
    const user = userEvent.setup();
    renderSettings("appearance");
    const toggle = screen.getByRole("switch", { name: "Reduce effects" });
    await user.click(toggle);
    expect(document.cookie).toContain("scentiq-effects=reduced");
    expect(readReduceEffects()).toBe(true);
    expect(router.refresh).toHaveBeenCalled();
    await user.click(toggle);
    expect(document.cookie).not.toContain("scentiq-effects=reduced");
    expect(within(screen.getByRole("group", { name: "Theme" })).getByRole("button", { name: "System" })).toBeInTheDocument();
  });
});
