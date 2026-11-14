import Link from "next/link";
import type { ReactNode } from "react";

import { accordVars } from "@/lib/accord";

import styles from "./auth.module.css";

const copy = {
  "sign-in": { title: "Welcome back", body: "Sign in to see what to wear today." },
  "sign-up": { title: "Make a shelf", body: "Add the bottles you own and start from there." },
} as const;

/**
 * Split layout for Clerk's sign-in and sign-up forms (Atelier interface).
 * The collage is decorative; on phones it becomes a short strip above the form.
 */
export function AtelierAuthFrame({ mode, children }: { mode: keyof typeof copy; children: ReactNode }) {
  const { title, body } = copy[mode];
  return (
    <main className={styles.frame}>
      <div className={styles.panel}>
        <Link href="/" className={styles.wordmark}>ScentIQ</Link>
        <div className={styles.collage} aria-hidden="true">
          <div className={`${styles.plate} ${styles.plateFresh}`} style={accordVars("fresh")} />
          <div className={`${styles.plate} ${styles.plateWoody}`} style={accordVars("woody")} />
        </div>
      </div>
      <div className={styles.column}>
        <div className={styles.form}>
          <h1 className="at-display-md">{title}</h1>
          <p className={`at-body-lg ${styles.lede}`}>{body}</p>
          {children}
        </div>
      </div>
    </main>
  );
}
