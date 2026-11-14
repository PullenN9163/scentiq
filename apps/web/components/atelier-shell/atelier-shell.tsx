"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSyncExternalStore, type ReactNode } from "react";

import { CommandMenu } from "@/components/app-shell/command-menu";
import { SegmentedControl } from "@/components/atelier/segmented-control";
import { cn } from "@/lib/utils";

import { AccountMenu } from "./account-menu";
import { ATELIER_DESTINATIONS, activeDestination } from "./navigation";
import styles from "./atelier-shell.module.css";

export const CATALOG_ATTRIBUTION =
  "Catalogue data includes Fragrantica data via Kaggle (ledecanteur/fragrantica-perfumes), CC BY-NC-SA 4.0, and Parfumo and Luckyscent listings.";

function openAsk() {
  window.dispatchEvent(new Event("scentiq:command"));
}

const noSubscription = () => () => {};

/** "⌘K" on Apple devices, "Ctrl K" elsewhere and during server rendering. */
function useShortcutLabel() {
  return useSyncExternalStore(
    noSubscription,
    () => (/Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent) ? "⌘K" : "Ctrl K"),
    () => "Ctrl K",
  );
}

/**
 * The Atelier navigation: a top bar from 700px (wordmark, the five
 * destinations, Ask, account) and, on phones, a header plus a floating dock
 * with Blend raised in the center.
 */
export function AtelierShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "/";
  const active = activeDestination(pathname);
  const shortcut = useShortcutLabel();
  return (
    <div className={styles.shell}>
      <a className={styles.skip} href="#main-content">Skip to content</a>
      <header className={styles.topBar}>
        <Link href="/dashboard" className={styles.wordmark}>ScentIQ</Link>
        <SegmentedControl
          label="Primary navigation"
          className={styles.destinations}
          value={active}
          segments={ATELIER_DESTINATIONS.map((destination) => ({ value: destination.value, label: destination.label, href: destination.href }))}
        />
        <div className={styles.topActions}>
          <button type="button" className={styles.askField} onClick={openAsk}>
            <i className={styles.askDot} aria-hidden="true" />
            <span className={styles.askLong}>Ask about your collection</span>
            <span className={styles.askShort}>Ask</span>
            <kbd className={styles.kbd} aria-hidden="true">{shortcut}</kbd>
          </button>
          <AccountMenu />
        </div>
      </header>
      <header className={styles.phoneHeader}>
        <Link href="/dashboard" className={styles.wordmark}>ScentIQ</Link>
        <div className={styles.topActions}>
          <button type="button" className={styles.askButton} onClick={openAsk}>
            <i className={styles.askDot} aria-hidden="true" />
            Ask
          </button>
          <AccountMenu />
        </div>
      </header>
      <main className={styles.main} id="main-content" tabIndex={-1}>
        {children}
        <footer className={cn("at-caption", styles.footer)}>{CATALOG_ATTRIBUTION}</footer>
      </main>
      <nav className={styles.dock} aria-label="Dock navigation">
        {ATELIER_DESTINATIONS.map((destination) => (
          <Link
            key={destination.value}
            href={destination.href}
            className={cn(styles.dockItem, destination.value === "blend" && styles.dockBlend)}
            aria-current={active === destination.value ? "page" : undefined}
          >
            <span>{destination.label}</span>
          </Link>
        ))}
      </nav>
      {/* The command menu keeps Ctrl/⌘ K and the "Ask ScentIQ" entry; its own launcher is hidden. */}
      <div className={styles.commandHost}><CommandMenu /></div>
    </div>
  );
}
