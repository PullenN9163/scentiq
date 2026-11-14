export type AtelierDestination = {
  value: "today" | "week" | "blend" | "collection" | "discover";
  href: string;
  label: string;
};

/** The five destinations, in order. Insights, Ask and Settings live elsewhere. */
export const ATELIER_DESTINATIONS: AtelierDestination[] = [
  { value: "today", href: "/dashboard", label: "Today" },
  { value: "week", href: "/week", label: "Week" },
  { value: "blend", href: "/layering", label: "Blend" },
  { value: "collection", href: "/collection", label: "Collection" },
  { value: "discover", href: "/discover", label: "Discover" },
];

/** The destination a path belongs to, or null for pages outside the five. */
export function activeDestination(pathname: string): AtelierDestination["value"] | null {
  for (const destination of ATELIER_DESTINATIONS) {
    if (pathname === destination.href || pathname.startsWith(`${destination.href}/`)) return destination.value;
  }
  return null;
}

/** Routes that run full screen without the top bar or the dock (the Blend studio). */
export function isStudioPath(pathname: string): boolean {
  return pathname === "/layering";
}
