import Link from "next/link";

import { FragranceRow } from "@/components/atelier/fragrance-row";
import { Plate } from "@/components/atelier/plate";
import { plateFragrance } from "@/components/atelier/plate-fragrance";
import { accordFor } from "@/lib/accord";
import { cn } from "@/lib/utils";
import type { TemperatureUnit } from "@/types/api";
import type { WearPlan } from "@/types/wear-intelligence";

import { selectedCandidate, weekGlance } from "./today-copy";
import styles from "./week-glance.module.css";

/**
 * "This week" on Today: three rows at 1100px and up, a strip of plates on
 * iPad portrait (six) and phones (five). Every entry opens the Week page.
 * With no plan, only the "Open week" link remains.
 */
export function WeekGlance({ plan, today, unit }: { plan: WearPlan | null; today: string; unit: TemperatureUnit | null | undefined }) {
  const entries = weekGlance(plan, today, unit);
  return (
    <section className={styles.section} aria-labelledby="this-week">
      <div className={styles.head}>
        <h2 id="this-week" className="at-title">This week</h2>
        <Link href="/week" className={styles.open}>Open week</Link>
      </div>
      {entries.length > 0 ? (
        <>
          <div className={styles.rows}>
            {entries.slice(0, 3).map((entry) => {
              const fragrance = selectedCandidate(entry.recommendation).fragrance;
              return (
                <FragranceRow
                  key={entry.date}
                  className={styles.row}
                  fragrance={plateFragrance(fragrance)}
                  accord={accordFor(fragrance)}
                  caption={entry.caption}
                  href="/week"
                  trailing={entry.forecast ? <span className="at-caption">{entry.forecast}</span> : null}
                />
              );
            })}
          </div>
          <ol className={styles.strip}>
            {entries.slice(0, 6).map((entry) => {
              const fragrance = selectedCandidate(entry.recommendation).fragrance;
              return (
                <li key={entry.date} className={styles.day}>
                  <Link href="/week" className={styles.dayLink} aria-label={`${entry.weekday}: ${fragrance.name}`}>
                    <Plate fragrance={plateFragrance(fragrance)} accord={accordFor(fragrance)} className={styles.dayPlate} decorative compact sizes="120px" />
                    <span className={cn("at-caption", styles.dayName)}>{entry.weekday}</span>
                  </Link>
                </li>
              );
            })}
          </ol>
        </>
      ) : null}
    </section>
  );
}

export function WeekGlanceSkeleton() {
  return (
    <section className={styles.section} aria-hidden="true">
      <div className={styles.head}><span className="at-skeleton" style={{ width: 140, height: 26 }} /></div>
      <div className={styles.skeletonRows}>
        {[0, 1, 2].map((index) => (
          <div key={index} className={styles.skeletonRow}>
            <span className="at-skeleton" style={{ width: 52, height: 60 }} />
            <span className="at-skeleton" style={{ width: 160, height: 16 }} />
          </div>
        ))}
      </div>
    </section>
  );
}
