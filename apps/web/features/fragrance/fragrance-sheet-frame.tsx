"use client";

import { ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

import { Sheet } from "@/components/atelier/sheet";

import { useFragranceNeighbours } from "./fragrance-list-context";
import styles from "./fragrance-sheet-frame.module.css";

/**
 * The fragrance sheet as an intercepted route. Closing goes back in history;
 * arrows step through the list that opened it; "Open full page" is a hard
 * navigation to the same address.
 */
export function FragranceSheetFrame({ id, title, fullHref, children }: { id: string; title: string; fullHref: string; children: ReactNode }) {
  const router = useRouter();
  const [open, setOpen] = useState(true);
  const { previous, next, position, total } = useFragranceNeighbours(id);
  function close(value: boolean) {
    if (value) return;
    setOpen(false);
    router.back();
  }
  const toolbar = (
    <div className={styles.toolbar}>
      {total > 0 ? (
        <>
          <button type="button" className={styles.icon} aria-label="Previous fragrance" disabled={!previous} onClick={() => previous && router.replace(`/collection/${previous}`, { scroll: false })}>
            <ChevronLeft aria-hidden="true" />
          </button>
          <button type="button" className={styles.icon} aria-label="Next fragrance" disabled={!next} onClick={() => next && router.replace(`/collection/${next}`, { scroll: false })}>
            <ChevronRight aria-hidden="true" />
          </button>
          <span className="at-caption">{position} of {total}</span>
        </>
      ) : null}
      {/* A plain anchor forces a full load, which renders the page rather than the sheet. */}
      <a href={fullHref} className={styles.full}>Open full page <ExternalLink aria-hidden="true" /></a>
    </div>
  );
  return (
    <Sheet open={open} onOpenChange={close} title={title} hideTitle toolbar={toolbar}>
      {children}
    </Sheet>
  );
}
