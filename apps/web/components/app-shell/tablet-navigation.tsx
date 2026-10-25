"use client";

import { UserButton } from "@clerk/nextjs";
import { Menu, Search, X } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { AppearanceControl } from "@/components/ui/theme-provider";
import { PRIMARY_DESTINATIONS, isDestinationActive } from "./navigation";

export type TabletNavigationProps = {
  pathname: string;
  displayName: string;
  email: string;
};

export function TabletNavigation({ pathname, displayName, email }: TabletNavigationProps) {
  const [open, setOpen] = useState(false);
  const shellRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!open) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    const closeOutside = (event: PointerEvent) => {
      if (event.target instanceof Node && !shellRef.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener("keydown", closeOnEscape);
    document.addEventListener("pointerdown", closeOutside);
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
      document.removeEventListener("pointerdown", closeOutside);
    };
  }, [open]);

  return (
    <aside className="tablet-shell" ref={shellRef}>
      <nav className="tablet-nav" aria-label="Tablet navigation">
        <Link href="/" className="tablet-nav__brand" aria-label="ScentIQ home">S</Link>
        <button
          type="button"
          className="tablet-nav__button"
          aria-label="Open navigation menu"
          aria-expanded={open}
          aria-controls="tablet-destinations"
          onClick={() => setOpen((value) => !value)}
        >
          {open ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
        </button>
        <div className="tablet-nav__destinations">
          {PRIMARY_DESTINATIONS.map(({ href, label, icon: Icon }) => {
            const active = isDestinationActive(pathname, href);
            return (
              <Link
                key={href}
                href={href}
                className="tablet-nav__link"
                aria-label={label}
                aria-current={active ? "page" : undefined}
                data-label={label}
              >
                {active && <motion.span className="nav-indicator tablet-nav__indicator" layoutId="tablet-active-nav" aria-hidden="true" />}
                <Icon size={21} aria-hidden="true" />
              </Link>
            );
          })}
        </div>
        <button type="button" className="tablet-nav__button tablet-nav__search" aria-label="Search ScentIQ" data-label="Search" onClick={() => window.dispatchEvent(new Event("scentiq:command"))}>
          <Search size={21} aria-hidden="true" />
        </button>
        <div className="tablet-nav__appearance"><AppearanceControl /></div>
        <div className="tablet-nav__account" aria-label={`${displayName} account`}><UserButton showName={false} /></div>
      </nav>
      {open ? (
        <section className="tablet-destination-panel" id="tablet-destinations">
          <div className="tablet-destination-panel__header">
            <div><span className="eyebrow">Navigate</span><strong>ScentIQ</strong></div>
            <button type="button" aria-label="Close navigation menu" onClick={() => setOpen(false)}><X size={18} /></button>
          </div>
          <nav className="side-nav" aria-label="Tablet destinations">
            {PRIMARY_DESTINATIONS.map(({ href, label, icon: Icon }) => {
              const active = isDestinationActive(pathname, href);
              return (
                <Link key={href} className="side-nav__link" href={href} aria-current={active ? "page" : undefined} onClick={() => setOpen(false)}>
                  <Icon size={18} aria-hidden="true" /><span>{label}</span>
                </Link>
              );
            })}
          </nav>
          <div className="tablet-destination-panel__profile"><strong>{displayName}</strong><small>{email}</small></div>
        </section>
      ) : null}
    </aside>
  );
}
