"use client";

import Link from "next/link";
import { LayoutGroup, motion } from "motion/react";
import { useId, type ReactNode } from "react";

import { motionTokens } from "@/lib/motion";
import { cn } from "@/lib/utils";

import styles from "./segmented-control.module.css";

export type Segment<T extends string> = {
  value: T;
  label: ReactNode;
  /** Short label for narrow screens. */
  shortLabel?: ReactNode;
  count?: number;
  href?: string;
};

/**
 * Switches between views of the same thing. The selected thumb slides
 * between positions as one shared element. Link segments mark the current
 * one with aria-current; button segments with aria-pressed.
 */
export function SegmentedControl<T extends string>({
  label,
  segments,
  value,
  onChange,
  className,
  size = "default",
}: {
  label: string;
  segments: Segment<T>[];
  value: T | null;
  onChange?: (value: T) => void;
  className?: string;
  size?: "default" | "compact";
}) {
  const id = useId();
  const content = (segment: Segment<T>, selected: boolean) => (
    <>
      {selected ? (
        <motion.span className={styles.thumb} layoutId={`segment-thumb-${id}`} transition={motionTokens.springSoft} aria-hidden="true" />
      ) : null}
      <span className={styles.label}>
        {segment.shortLabel ? (
          <>
            <span className={styles.long}>{segment.label}</span>
            <span className={styles.short}>{segment.shortLabel}</span>
          </>
        ) : (
          segment.label
        )}
        {segment.count !== undefined ? <>{" "}<span className={styles.count}>{segment.count}</span></> : null}
      </span>
    </>
  );
  const isNav = segments.some((segment) => segment.href);
  const items = segments.map((segment) => {
    const selected = segment.value === value;
    return segment.href ? (
      <Link key={segment.value} href={segment.href} className={cn(styles.segment, selected && styles.selected)} aria-current={selected ? "page" : undefined}>
        {content(segment, selected)}
      </Link>
    ) : (
      <button
        key={segment.value}
        type="button"
        className={cn(styles.segment, selected && styles.selected)}
        aria-pressed={selected}
        onClick={() => onChange?.(segment.value)}
      >
        {content(segment, selected)}
      </button>
    );
  });
  return (
    <LayoutGroup id={id}>
      {isNav ? (
        <nav aria-label={label} className={cn(styles.track, size === "compact" && styles.compact, className)}>{items}</nav>
      ) : (
        <div role="group" aria-label={label} className={cn(styles.track, size === "compact" && styles.compact, className)}>{items}</div>
      )}
    </LayoutGroup>
  );
}
