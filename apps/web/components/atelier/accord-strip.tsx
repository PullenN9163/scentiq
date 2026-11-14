import { accordFromLabel, type AccordKey } from "@/lib/accord";
import { cn } from "@/lib/utils";

import styles from "./accord-strip.module.css";

export type AccordShare = { label: string; share: number };

export type StripSegment = { label: string; share: number; key: AccordKey | "other" };

/** Up to five accords by share, the rest grouped as "Other"; shares sum to 1. */
export function stripSegments(accords: readonly AccordShare[], limit = 5): StripSegment[] {
  const positive = accords.filter((accord) => accord.share > 0);
  const total = positive.reduce((sum, accord) => sum + accord.share, 0);
  if (total <= 0) return [];
  const sorted = [...positive].sort((a, b) => b.share - a.share);
  // Shares that already sum to at most 1 are kept as they are, with the
  // remainder shown as Other; larger sums (weights) are normalised.
  const denominator = total > 1.0001 ? total : 1;
  const top = sorted.slice(0, limit).map((accord) => ({ label: accord.label, share: accord.share / denominator, key: accordFromLabel(accord.label) as AccordKey | "other" }));
  const rest = 1 - top.reduce((sum, segment) => sum + segment.share, 0);
  return rest > 0.005 ? [...top, { label: "Other", share: rest, key: "other" }] : top;
}

function segmentColor(key: AccordKey | "other"): string {
  if (key === "other") return "var(--ink-muted)";
  return `var(--chart-${key === "neutral" ? "musk" : key})`;
}

/** "Musky 55% · Woody 25% · Fresh 20%" */
export function stripLegend(segments: readonly StripSegment[]): string {
  return segments.map((segment) => `${segment.label} ${Math.round(segment.share * 100)}%`).join(" · ");
}

/**
 * One rounded bar split by share, labelled in text beneath. Colors are the
 * chart tokens of each accord's family; color is never the only key.
 */
export function AccordStrip({ accords, className, legend = true }: { accords: readonly AccordShare[]; className?: string; legend?: boolean }) {
  const segments = stripSegments(accords);
  if (segments.length === 0) return null;
  return (
    <figure className={cn(styles.figure, className)}>
      <div className={styles.bar} aria-hidden="true">
        {segments.map((segment) => (
          <span key={segment.label} className={styles.segment} style={{ flexGrow: segment.share, background: segmentColor(segment.key) }} />
        ))}
      </div>
      {legend ? <figcaption className="at-caption">{stripLegend(segments)}</figcaption> : <figcaption className="sr-only">{stripLegend(segments)}</figcaption>}
    </figure>
  );
}
