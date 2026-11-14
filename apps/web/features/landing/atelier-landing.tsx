import { SignedIn, SignedOut } from "@clerk/nextjs";
import Link from "next/link";

import { Button } from "@/components/atelier";
import { accordVars, type AccordKey } from "@/lib/accord";

import styles from "./landing.module.css";

/** Static accord plates for the hero. No photographs and no claims. */
const collage: { accord: AccordKey; position: "back" | "top" | "front" }[] = [
  { accord: "amber", position: "back" },
  { accord: "woody", position: "top" },
  { accord: "fresh", position: "front" },
];

const steps = [
  ["Add what you own", "Bottles, decants and samples."],
  ["Share your day", "Location and calendar, only what is needed."],
  ["Wear the pick", "Respond once and it learns."],
] as const;

/** Public landing page for the Atelier interface (flag on). */
export function AtelierLanding() {
  return (
    <main className={styles.landing}>
      <header className={styles.nav}>
        <Link href="/" className={styles.wordmark}>ScentIQ</Link>
        <div className={styles.navActions}>
          <SignedIn>
            <Button asChild><Link href="/dashboard">Open ScentIQ</Link></Button>
          </SignedIn>
          <SignedOut>
            <Button asChild variant="text"><Link href="/sign-in">Sign in</Link></Button>
            <Button asChild><Link href="/sign-up">Get started</Link></Button>
          </SignedOut>
        </div>
      </header>

      <section className={styles.hero} aria-labelledby="landing-title">
        <div className={styles.copy}>
          <h1 id="landing-title" className="at-display-xl">Wear the scent your day calls for.</h1>
          <p className="at-body-lg">ScentIQ looks at your collection, the weather and your calendar, and picks.</p>
          <div className={styles.actions}>
            <SignedIn>
              <Button asChild><Link href="/dashboard">Open ScentIQ</Link></Button>
            </SignedIn>
            <SignedOut>
              <Button asChild><Link href="/sign-up">Get started</Link></Button>
              <Button asChild variant="text"><Link href="/sign-in">Sign in</Link></Button>
            </SignedOut>
          </div>
        </div>
        <div className={styles.collage} aria-hidden="true">
          {collage.map(({ accord, position }) => (
            <div key={accord} className={`${styles.plate} ${styles[position]}`} style={accordVars(accord)} />
          ))}
        </div>
      </section>

      <section className={styles.steps} aria-label="How it works">
        <ol className={styles.stepList}>
          {steps.map(([title, body], index) => (
            <li key={title} className={styles.step}>
              <span className={`at-numeral ${styles.numeral}`} aria-hidden="true">{index + 1}</span>
              <h2>{title}</h2>
              <p>{body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className={styles.band} data-theme="dark" aria-labelledby="studio-title">
        <div>
          <h2 id="studio-title" className="at-display-lg">Blend two scents into one.</h2>
          <p className="at-body-lg">Pour, tilt, save. Your own cabinet of combinations.</p>
        </div>
        <Button asChild><Link href="/layering">Open the studio</Link></Button>
      </section>
    </main>
  );
}
