"use client";

import { BarChart3, Beaker, CalendarDays, Compass, Home, Menu, Settings, Sparkles, UserRound, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { demoUser } from "@/lib/demo";

const primary = [
  { href: "/dashboard", label: "Today", icon: Home },
  { href: "/week", label: "My Week", icon: CalendarDays },
  { href: "/collection", label: "Collection", icon: Sparkles },
  { href: "/layering", label: "Layering Lab", icon: Beaker },
  { href: "/discover", label: "Discover", icon: Compass },
  { href: "/insights", label: "Insights", icon: BarChart3 },
  { href: "/agent", label: "Agent", icon: UserRound },
  { href: "/settings", label: "Settings", icon: Settings },
];

const mobile = primary.filter(({ href }) => ["/dashboard", "/week", "/collection", "/discover"].includes(href));
const more = primary.filter(({ href }) => ["/layering", "/insights", "/agent", "/settings"].includes(href));

function NavLink({ href, label, icon: Icon, pathname, compact = false }: (typeof primary)[number] & { pathname: string; compact?: boolean }) {
  const active = pathname === href || (href === "/collection" && pathname.startsWith("/collection/"));
  return (
    <Link className={compact ? "bottom-nav__link" : "side-nav__link"} href={href} aria-current={active ? "page" : undefined}>
      <Icon size={compact ? 20 : 18} aria-hidden="true" />
      <span>{label === "My Week" && compact ? "Week" : label}</span>
    </Link>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [moreOpen, setMoreOpen] = useState(false);
  return (
    <div className="app-frame">
      <aside className="sidebar">
        <Link href="/" className="brand"><span className="brand__mark">S</span><span>ScentIQ</span></Link>
        <Badge className="sidebar__demo">Demo mode</Badge>
        <nav className="side-nav" aria-label="Primary navigation">
          {primary.map((item) => <NavLink key={item.href} {...item} pathname={pathname} />)}
        </nav>
        <div className="sidebar__profile"><span className="avatar">{demoUser.initials}</span><span><strong>{demoUser.name}</strong><small>{demoUser.location}</small></span></div>
      </aside>
      <header className="mobile-header">
        <Link href="/" className="brand"><span className="brand__mark">S</span><span>ScentIQ</span></Link>
        <Badge>Demo</Badge>
      </header>
      <main className="app-main">{children}</main>
      {moreOpen && (
        <div className="more-panel" role="dialog" aria-label="More destinations">
          <div className="more-panel__header"><strong>More</strong><button type="button" onClick={() => setMoreOpen(false)} aria-label="Close more destinations"><X size={20} /></button></div>
          <nav className="more-panel__grid" aria-label="Secondary navigation">
            {more.map((item) => <NavLink key={item.href} {...item} pathname={pathname} />)}
          </nav>
        </div>
      )}
      <nav className="bottom-nav" aria-label="Mobile navigation">
        {mobile.map((item) => <NavLink key={item.href} {...item} pathname={pathname} compact />)}
        <button type="button" className="bottom-nav__link" onClick={() => setMoreOpen((open) => !open)} aria-expanded={moreOpen} aria-label="More destinations"><Menu size={20} /><span>More</span></button>
      </nav>
    </div>
  );
}
