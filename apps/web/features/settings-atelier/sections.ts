// Plain module on purpose: the Settings page (a server component) calls sectionFrom.

export const SECTIONS = [
  { id: "profile", label: "Profile" },
  { id: "taste", label: "Taste" },
  { id: "place", label: "Place and weather" },
  { id: "calendar", label: "Calendars" },
  { id: "appearance", label: "Appearance" },
  { id: "account", label: "Account" },
] as const;
export type SectionId = (typeof SECTIONS)[number]["id"];

/** `?section=` wins, then the hash (existing links use /settings#calendar). */
export function sectionFrom(search: string | null | undefined, hash: string | null | undefined): SectionId | null {
  const known = (value: string | null | undefined) => SECTIONS.find((section) => section.id === value)?.id ?? null;
  const param = search ? new URLSearchParams(search).get("section") : null;
  const fromHash = hash ? hash.replace(/^#/, "") : null;
  return known(param) ?? known(fromHash === "calendars" ? "calendar" : fromHash);
}
