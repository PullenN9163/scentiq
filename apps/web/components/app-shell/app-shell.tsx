"use client";

import { UserButton, useUser } from "@clerk/nextjs";
import { Menu, Search } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useState } from "react";
import { motion } from "motion/react";
import { CommandMenu } from "./command-menu";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { AppearanceControl } from "@/components/ui/theme-provider";
import { MORE_DESTINATIONS, PHONE_DESTINATIONS, PRIMARY_DESTINATIONS, isDestinationActive, type NavDestination } from "./navigation";
import { TabletNavigation } from "./tablet-navigation";

function NavLink({ href, label, icon: Icon, pathname, compact = false, onNavigate }: NavDestination & { pathname: string; compact?: boolean; onNavigate?: () => void }) {
  const active = isDestinationActive(pathname, href);
  return (
    <Link className={compact ? "bottom-nav__link" : "side-nav__link"} href={href} aria-current={active ? "page" : undefined} onClick={onNavigate}>
      {active && <motion.span className={compact ? "nav-indicator nav-indicator--mobile" : "nav-indicator"} layoutId={compact ? "mobile-active-nav" : onNavigate ? "more-active-nav" : "desktop-active-nav"} aria-hidden="true" />}
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
      <a className="skip-link" href="#main-content">Skip to content</a>
      <aside className="sidebar">
        <Link href="/" className="brand"><span className="brand__mark">S</span><span>ScentIQ</span></Link>
        <Badge className="sidebar__demo">Private beta</Badge>
        <CommandMenu />
        <nav className="side-nav" aria-label="Primary navigation">
          {PRIMARY_DESTINATIONS.map((item) => <NavLink key={item.href} {...item} pathname={pathname} />)}
        </nav>
        <div className="sidebar__appearance"><AppearanceControl /></div>
        <div className="sidebar__profile"><UserButton showName={false} /><span><strong>{displayName}</strong><small>{user?.primaryEmailAddress?.emailAddress ?? ""}</small></span></div>
      </aside>
      <TabletNavigation pathname={pathname} displayName={displayName} email={user?.primaryEmailAddress?.emailAddress ?? ""} />
      <header className="mobile-header">
        <Link href="/" className="brand"><span className="brand__mark">S</span><span>ScentIQ</span></Link>
        <AppearanceControl />
        <Button variant="ghost" aria-label="Search ScentIQ" onClick={() => window.dispatchEvent(new Event("scentiq:command"))}><Search size={18} /></Button>
      </header>
      <main className="app-main" id="main-content" tabIndex={-1}>{children}<footer className="data-note app-footer">Catalogue data includes Fragrantica data via Kaggle (ledecanteur/fragrantica-perfumes), CC BY-NC-SA 4.0, and Parfumo and Luckyscent listings.</footer></main>
      <DialogContent title="More destinations" className="more-panel">
          <nav className="more-panel__grid" aria-label="Secondary navigation">
            {MORE_DESTINATIONS.map((item) => <NavLink key={item.href} {...item} pathname={pathname} onNavigate={() => setMoreOpen(false)} />)}
          </nav>
      </DialogContent>
      <nav className="bottom-nav" aria-label="Mobile navigation">
        {PHONE_DESTINATIONS.map((item) => <NavLink key={item.href} {...item} pathname={pathname} compact />)}
        <DialogTrigger asChild><button type="button" className="bottom-nav__link" aria-expanded={moreOpen} aria-label="More destinations"><Menu size={20} /><span>More</span></button></DialogTrigger>
      </nav>
    </div>
    </Dialog>
  );
}
