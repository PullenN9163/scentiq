"use client";

import { useClerk, useUser } from "@clerk/nextjs";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import Link from "next/link";

import { useThemePreference, type ThemePreference } from "@/components/ui/theme-provider";

import styles from "./atelier-shell.module.css";

const APPEARANCE: { value: ThemePreference; label: string }[] = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

function initials(name: string | null | undefined): string {
  if (!name) return "";
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

/**
 * The account menu: Your taste, Settings, appearance, and the Clerk account
 * controls (manage account, sign out).
 */
export function AccountMenu() {
  const { user } = useUser();
  const clerk = useClerk();
  const { preference, setPreference } = useThemePreference();
  const name = user?.fullName ?? user?.username ?? null;
  const email = user?.primaryEmailAddress?.emailAddress ?? null;
  return (
    <DropdownMenu.Root modal={false}>
      <DropdownMenu.Trigger className={styles.avatar} aria-label="Account menu">
        <span aria-hidden="true">{initials(name) || "·"}</span>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content className={styles.menu} align="end" sideOffset={8} collisionPadding={16}>
          {name || email ? (
            <div className={styles.menuWho}>
              {name ? <span className="at-label">{name}</span> : null}
              {email ? <span className="at-caption">{email}</span> : null}
            </div>
          ) : null}
          <DropdownMenu.Item asChild className={styles.menuItem}>
            <Link href="/insights">Your taste</Link>
          </DropdownMenu.Item>
          <DropdownMenu.Item asChild className={styles.menuItem}>
            <Link href="/settings">Settings</Link>
          </DropdownMenu.Item>
          <DropdownMenu.Separator className={styles.menuLine} />
          <DropdownMenu.Label className={`at-caption ${styles.menuLabel}`}>Appearance</DropdownMenu.Label>
          <DropdownMenu.RadioGroup value={preference} onValueChange={(value) => setPreference(value as ThemePreference)} className={styles.menuRadios}>
            {APPEARANCE.map((choice) => (
              <DropdownMenu.RadioItem key={choice.value} value={choice.value} className={styles.menuRadio}>
                {choice.label}
              </DropdownMenu.RadioItem>
            ))}
          </DropdownMenu.RadioGroup>
          <DropdownMenu.Separator className={styles.menuLine} />
          <DropdownMenu.Item className={styles.menuItem} onSelect={() => clerk.openUserProfile?.()}>
            Manage account
          </DropdownMenu.Item>
          <DropdownMenu.Item className={styles.menuItem} onSelect={() => void clerk.signOut?.({ redirectUrl: "/" })}>
            Sign out
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
