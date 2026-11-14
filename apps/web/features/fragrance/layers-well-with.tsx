import Link from "next/link";

import { Plate, plateFragrance } from "@/components/atelier/plate";
import { accordFor } from "@/lib/accord";
import type { LayeringStackSuggestion } from "@/types/layering";

import styles from "./fragrance.module.css";

type Partner = { fragrance: LayeringStackSuggestion["items"][number]["fragrance"]; mode: LayeringStackSuggestion["mode"] };

/** Up to three distinct partners for an anchor, best suggestion first. */
export function layeringPartners(anchorId: string, suggestions: readonly LayeringStackSuggestion[], limit = 3): Partner[] {
  const seen = new Set<string>([anchorId]);
  const partners: Partner[] = [];
  for (const suggestion of [...suggestions].sort((a, b) => b.score - a.score)) {
    for (const item of [...suggestion.items].sort((a, b) => a.application_order - b.application_order)) {
      if (seen.has(item.fragrance.id)) continue;
      seen.add(item.fragrance.id);
      partners.push({ fragrance: item.fragrance, mode: suggestion.mode });
      if (partners.length >= limit) return partners;
    }
  }
  return partners;
}

/** "Layers well with": partner chips and one link into Blend. Hidden with no partners. */
export function LayersWellWith({ anchorId, suggestions }: { anchorId: string; suggestions: readonly LayeringStackSuggestion[] }) {
  const partners = layeringPartners(anchorId, suggestions);
  if (partners.length === 0) return null;
  return (
    <section className={styles.section} aria-labelledby={`${anchorId}-layers`}>
      <h3 id={`${anchorId}-layers`} className={styles.heading}>
        Layers well with
        <Link className={styles.headingLink} href={`/layering?a=${anchorId}`}>Open in Blend →</Link>
      </h3>
      <div className={styles.pairs}>
        {partners.map(({ fragrance, mode }) => (
          <Link key={fragrance.id} className={styles.pair} href={`/layering?stack=${anchorId},${fragrance.id}&mode=${mode}`}>
            <Plate fragrance={plateFragrance(fragrance)} accord={accordFor(fragrance)} className={styles.pairPlate} decorative compact sizes="28px" />
            <span>{fragrance.name}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}

export function LayersWellWithSkeleton() {
  return (
    <section className={styles.section} aria-hidden="true">
      <span className="at-skeleton" style={{ width: 140, height: 18 }} />
      <div className={styles.pairs}>
        {[0, 1, 2].map((index) => <span key={index} className="at-skeleton" style={{ flex: 1, height: 50 }} />)}
      </div>
    </section>
  );
}
