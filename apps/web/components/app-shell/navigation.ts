import {
  BarChart3,
  Beaker,
  CalendarDays,
  Compass,
  Home,
  Settings,
  Sparkles,
  UserRound,
  type LucideIcon,
} from "lucide-react";

export type NavDestination = {
  href: string;
  label: string;
  icon: LucideIcon;
};

export const PRIMARY_DESTINATIONS: NavDestination[] = [
  { href: "/dashboard", label: "Today", icon: Home },
  { href: "/week", label: "My Week", icon: CalendarDays },
  { href: "/collection", label: "Collection", icon: Sparkles },
  { href: "/layering", label: "Layering Lab", icon: Beaker },
  { href: "/discover", label: "Discover", icon: Compass },
  { href: "/insights", label: "Insights", icon: BarChart3 },
  { href: "/agent", label: "Agent", icon: UserRound },
  { href: "/settings", label: "Settings", icon: Settings },
];

export const PHONE_DESTINATIONS = PRIMARY_DESTINATIONS.filter(({ href }) =>
  ["/dashboard", "/week", "/collection", "/discover"].includes(href),
);

export const MORE_DESTINATIONS = PRIMARY_DESTINATIONS.filter(({ href }) =>
  ["/layering", "/insights", "/agent", "/settings"].includes(href),
);

export function isDestinationActive(pathname: string, href: string) {
  return pathname === href || (href === "/collection" && pathname.startsWith("/collection/"));
}
