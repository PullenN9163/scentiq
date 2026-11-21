"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";

import type { AccordKey } from "@/lib/accord";
import { cn } from "@/lib/utils";

import { Plate, type PlateFragrance } from "./plate";
import styles from "./fragrance-card.module.css";

export type QuickAction = {
  label: string;
  href?: string;
  onSelect?: () => void;
  disabled?: boolean;
};

const LONG_PRESS_MS = 450;

/**
 * The grid form of a fragrance: plate, name and caption, no border or shadow.
 * The whole card opens the fragrance. Hover (pointer) or long-press (touch)
 * reveals the quick actions on the plate; they are also reachable by keyboard
 * and always exist again inside the fragrance sheet.
 */
export function FragranceCard({
  fragrance,
  accord,
  caption,
  status,
  href,
  onOpen,
  actions = [],
  selected = false,
  layoutId,
  priority = false,
  corner,
  className,
}: {
  fragrance: PlateFragrance;
  accord: AccordKey;
  /** Defaults to the house name. */
  caption?: ReactNode;
  /** A short status ("Nearly empty", "Wishlist") appended to the caption. */
  status?: string | null;
  href?: string;
  onOpen?: () => void;
  actions?: QuickAction[];
  selected?: boolean;
  layoutId?: string;
  priority?: boolean;
  /** An extra control pinned to the plate's top-right corner, such as a heart. */
  corner?: ReactNode;
  className?: string;
}) {
  const [actionsOpen, setActionsOpen] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const longPressed = useRef(false);
  const root = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!actionsOpen) return;
    const close = (event: PointerEvent) => {
      if (root.current && !root.current.contains(event.target as Node)) setActionsOpen(false);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [actionsOpen]);

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  function cancelPress() {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  }

  const captionText = caption ?? fragrance.brand;
  const title = <span className={cn("at-card-title", styles.name)}>{fragrance.name}</span>;
  return (
    <article
      ref={root}
      className={cn(styles.card, selected && styles.selected, className)}
      data-actions-open={actionsOpen ? "true" : "false"}
      data-testid="fragrance-card"
      onPointerDown={(event) => {
        if (event.pointerType !== "touch" || actions.length === 0) return;
        longPressed.current = false;
        cancelPress();
        timer.current = setTimeout(() => {
          longPressed.current = true;
          setActionsOpen(true);
        }, LONG_PRESS_MS);
      }}
      onPointerUp={cancelPress}
      onPointerCancel={cancelPress}
      onPointerLeave={cancelPress}
      onContextMenu={(event) => { if (actions.length > 0 && longPressed.current) event.preventDefault(); }}
      onClickCapture={(event) => {
        // The click that ends a long press only reveals the actions.
        if (longPressed.current) {
          longPressed.current = false;
          if (!(event.target as HTMLElement).closest("[data-quick-action]")) {
            event.preventDefault();
            event.stopPropagation();
          }
        }
      }}
    >
      <div className={styles.plateWrap}>
        <Plate fragrance={fragrance} accord={accord} className={styles.plate} decorative layoutId={layoutId} priority={priority} />
        {corner ? <div className={styles.corner}>{corner}</div> : null}
        {actions.length > 0 ? (
          <div className={styles.quick}>
            {actions.map((action) =>
              action.href ? (
                <Link key={action.label} href={action.href} className={styles.quickButton} data-quick-action>
                  {action.label}
                </Link>
              ) : (
                <button
                  key={action.label}
                  type="button"
                  className={styles.quickButton}
                  data-quick-action
                  disabled={action.disabled}
                  onClick={() => { setActionsOpen(false); action.onSelect?.(); }}
                >
                  {action.label}
                </button>
              ),
            )}
          </div>
        ) : null}
      </div>
      {href ? (
        <Link href={href} className={styles.open} onClick={onOpen}>{title}</Link>
      ) : onOpen ? (
        <button type="button" className={styles.open} onClick={onOpen}>{title}</button>
      ) : (
        title
      )}
      <span className={cn("at-caption", styles.caption)}>
        {captionText}
        {status ? <> · <span className={styles.status}>{status}</span></> : null}
      </span>
    </article>
  );
}
