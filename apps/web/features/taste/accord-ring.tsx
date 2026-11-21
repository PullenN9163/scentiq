"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";

import type { StripSegment } from "@/components/atelier/accord-strip";

import styles from "./taste.module.css";

const SIZE = 240;
const RADIUS = 96;
const STROKE = 26;
const GAP = 0.012;

function point(angle: number): [number, number] {
  return [SIZE / 2 + RADIUS * Math.cos(angle), SIZE / 2 + RADIUS * Math.sin(angle)];
}

function arc(start: number, end: number): string {
  const a = start * Math.PI * 2 - Math.PI / 2;
  const b = end * Math.PI * 2 - Math.PI / 2;
  const [x1, y1] = point(a);
  const [x2, y2] = point(b);
  const large = end - start > 0.5 ? 1 : 0;
  return `M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${RADIUS} ${RADIUS} 0 ${large} 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`;
}

export function segmentColor(key: StripSegment["key"]): string {
  if (key === "other") return "var(--line-strong)";
  return `var(--chart-${key === "neutral" ? "musk" : key})`;
}

/**
 * The accord ring: one arc per accord, colored with its chart token. It draws
 * in once on first view (skipped under reduced motion). Decorative; the
 * legend carries the same numbers in text.
 */
export function AccordRing({ segments, selected }: { segments: StripSegment[]; selected: number }) {
  const reduced = useReducedMotion();

  const arcs = segments.map((segment, index) => {
    const start = segments.slice(0, index).reduce((sum, previous) => sum + previous.share, 0);
    const end = start + segment.share;
    return { segment, start, end: Math.max(start + 0.001, end - (segments.length > 1 ? GAP : 0)) };
  });
  const current = segments[selected] ?? segments[0];
  return (
    <div className={styles.ring}>
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} aria-hidden="true" focusable="false">
        <circle cx={SIZE / 2} cy={SIZE / 2} r={RADIUS} fill="none" stroke="var(--surface-sunken)" strokeWidth={STROKE} />
        {arcs.map(({ segment, start, end }, index) => (
          <motion.path
            key={segment.label}
            d={arc(start, end)}
            fill="none"
            stroke={segmentColor(segment.key)}
            strokeWidth={index === selected ? STROKE + 6 : STROKE}
            strokeLinecap="butt"
            initial={reduced ? false : { pathLength: 0 }}
            animate={{ pathLength: 1, opacity: index === selected || selected < 0 ? 1 : 0.8 }}
            transition={{ pathLength: { duration: 0.4, delay: reduced ? 0 : start * 0.4, ease: "easeOut" }, opacity: { duration: 0.2 } }}
          />
        ))}
      </svg>
      {current ? (
        <div className={styles.ringCenter}>
          <AnimatePresence mode="wait" initial={false}>
            <motion.span key={current.label} className={styles.ringNumber} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.15 }}>
              {Math.round(current.share * 100)}%
            </motion.span>
          </AnimatePresence>
          <span className="at-caption">{current.label}</span>
        </div>
      ) : null}
    </div>
  );
}
