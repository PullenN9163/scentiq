"use client";

import { UserButton, useUser } from "@clerk/nextjs";
import { BarChart3, Beaker, CalendarDays, Compass, Home, Menu, Settings, Sparkles, UserRound } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";

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

function NavLink({ href, label, icon: Icon, pathname, compact = false, onNavigate }: (typeof primary)[number] & { pathname: string; compact?: boolean; onNavigate?: () => void }) {
  const active = pathname === href || (href === "/collection" && pathname.startsWith("/collection/"));
  return (
    <Link className={compact ? "bottom-nav__link" : "side-nav__link"} href={href} aria-current={active ? "page" : undefined} onClick={onNavigate}>
      <Icon size={compact ? 20 : 18} aria-hidden="true" />
      <span>{label === "My Week" && compact ? "Week" : label}</span>
    </Link>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user } = useUser();
  const [moreOpen, setMoreOpen] = useState(false);
  // Clerk is the source of truth for who is signed in.
  const displayName = user?.fullName ?? user?.username ?? "Your account";
  return (
    <Dialog open={moreOpen} onOpenChange={setMoreOpen}>
    <div className="app-frame">
      <aside className="sidebar">
        <Link href="/" className="brand"><span className="brand__mark">S</span><span>ScentIQ</span></Link>
        <Badge className="sidebar__demo">Private beta</Badge>
        <nav className="side-nav" aria-label="Primary navigation">
          {primary.map((item) => <NavLink key={item.href} {...item} pathname={pathname} />)}
        </nav>
        <div className="sidebar__profile"><UserButton showName={false} /><span><strong>{displayName}</strong><small>{user?.primaryEmailAddress?.emailAddress ?? ""}</small></span></div>
      </aside>
      <header className="mobile-header">
        <Link href="/" className="brand"><span className="brand__mark">S</span><span>ScentIQ</span></Link>
        <Badge>Beta</Badge>
      </header>
      <main className="app-main">{children}</main>
      <DialogContent title="More destinations" className="more-panel">
          <nav className="more-panel__grid" aria-label="Secondary navigation">
            {more.map((item) => <NavLink key={item.href} {...item} pathname={pathname} onNavigate={() => setMoreOpen(false)} />)}
          </nav>
      </DialogContent>
      <nav className="bottom-nav" aria-label="Mobile navigation">
        {mobile.map((item) => <NavLink key={item.href} {...item} pathname={pathname} compact />)}
        <DialogTrigger asChild><button type="button" className="bottom-nav__link" aria-expanded={moreOpen} aria-label="More destinations"><Menu size={20} /><span>More</span></button></DialogTrigger>
      </nav>
    </div>
    </Dialog>
  );
}
