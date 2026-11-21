"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import type { AccordKey } from "@/lib/accord";
import { cn } from "@/lib/utils";

import { Plate, type PlateFragrance } from "./plate";
import styles from "./fragrance-row.module.css";

/**
 * A fragrance as a list row: a 52 by 60px plate, the name in card-title, a
 * caption and one trailing slot. With `href` or `onOpen`, the plate and text
 * open the fragrance; the trailing slot stays its own control.
 */
export function FragranceRow({
  fragrance,
  accord,
  caption,
  trailing,
  href,
  onOpen,
  className,
  captionFirst = false,
  layoutId,
}: {
  fragrance: PlateFragrance;
  accord: AccordKey;
  caption?: ReactNode;
  trailing?: ReactNode;
  href?: string;
  onOpen?: () => void;
  className?: string;
  /** Print the caption above the name (used for "Tonight · Dinner" style rows). */
  captionFirst?: boolean;
  layoutId?: string;
}) {
  const body = (
    <>
      <Plate fragrance={fragrance} accord={accord} className={styles.plate} decorative compact sizes="52px" layoutId={layoutId} />
      <span className={styles.text}>
        {captionFirst && caption ? <span className="at-caption">{caption}</span> : null}
        <span className={cn("at-card-title", styles.name)}>{fragrance.name}</span>
        {!captionFirst && caption ? <span className="at-caption">{caption}</span> : null}
      </span>
    </>
  );
  return (
    <div className={cn(styles.row, className)} data-testid="fragrance-row">
      {href ? (
        <Link href={href} className={styles.main} onClick={onOpen}>
          {body}
        </Link>
      ) : onOpen ? (
        <button type="button" className={styles.main} onClick={onOpen}>
          {body}
        </button>
      ) : (
        <div className={styles.main}>{body}</div>
      )}
      {trailing ? <div className={styles.trailing}>{trailing}</div> : null}
    </div>
  );
}
