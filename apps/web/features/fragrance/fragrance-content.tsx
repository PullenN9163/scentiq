"use client";

import Link from "next/link";
import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";

import { AccordStrip } from "@/components/atelier/accord-strip";
import { Chip } from "@/components/atelier/chip";
import { FragranceCard } from "@/components/atelier/fragrance-card";
import { Plate, plateFragrance } from "@/components/atelier/plate";
import { CATALOG_ATTRIBUTION } from "@/lib/attribution";
import { CustomImageUpload } from "@/features/collection/custom-image-upload";
import { accordFor, accordVars } from "@/lib/accord";
import { cn } from "@/lib/utils";
import type { FragrancePageData } from "@/types/api";

import { FragranceActions, ownershipOf } from "./fragrance-actions";
import { notesByStage, personalLine, weeklyWears } from "./fragrance-copy";
import styles from "./fragrance.module.css";

/**
 * One fragrance, owned or from the catalog. Shared by the sheet and the full
 * page; sections with no data are left out.
 */
export function FragranceContent({
  data,
  variant,
  layersWell,
  back,
}: {
  data: FragrancePageData;
  variant: "sheet" | "page";
  /** "Layers well with", streamed in its own Suspense boundary. */
  layersWell?: ReactNode;
  back?: { href: string; label: string };
}) {
  const { fragrance, collection_item: item, recent_wears: wears } = data;
  const accord = accordFor(fragrance);
  const groups = notesByStage(fragrance.notes);
  const line = personalLine(fragrance, item, wears);
  const owned = ownershipOf(item) === "owned" || ownershipOf(item) === "retired";
  const weeks = weeklyWears(wears);
  const weekTotal = weeks.reduce((sum, count) => sum + count, 0);
  const peak = Math.max(1, ...weeks);
  const community = fragrance.community;
  const communityFacts = [
    community?.longevity_average != null ? `Longevity ${community.longevity_average.toFixed(1)} of 5` : null,
    community?.sillage_average != null ? `Sillage ${community.sillage_average.toFixed(1)} of 4` : null,
    community?.price_value_average != null ? `Value ${community.price_value_average.toFixed(1)} of 5` : null,
    fragrance.rating_average != null ? `Rated ${fragrance.rating_average.toFixed(1)} of 5${fragrance.rating_count ? ` by ${fragrance.rating_count.toLocaleString("en-GB")}` : ""}` : null,
  ].filter(Boolean) as string[];
  const Name = variant === "page" ? "h1" : "h2";

  return (
    <article className={cn(styles.content, variant === "page" ? styles.page : styles.sheet)} style={accordVars(accord)} data-testid="fragrance-content">
      {back ? <Link href={back.href} className={styles.back}>‹ {back.label}</Link> : null}
      <header className={styles.hero}>
        <div className={styles.heroPlate}>
          <Plate fragrance={plateFragrance(fragrance)} accord={accord} className={styles.plate} layoutId={`plate-${fragrance.id}`} priority sizes={variant === "page" ? "(max-width: 700px) 90vw, 520px" : "160px"} />
          {fragrance.is_custom && variant === "page" ? <CustomImageUpload fragranceId={fragrance.id} hasImage={Boolean(fragrance.image_blob_path)} /> : null}
        </div>
        <div className={styles.heroText}>
          <p className="at-overline">{fragrance.brand.name}</p>
          <Name className={cn(variant === "page" ? "at-display-lg" : "at-display-md", styles.name)}>{fragrance.name}</Name>
          {line ? <p className={styles.line}>{line}</p> : null}
          <FragranceActions fragrance={fragrance} item={item} compact={variant === "sheet"} />
        </div>
      </header>

      {groups.length > 0 ? (
        <section className={styles.section} aria-labelledby={`${fragrance.id}-notes`}>
          <h3 id={`${fragrance.id}-notes`} className={styles.heading}>Notes</h3>
          <dl className={styles.notes}>
            {groups.map((group) => (
              <div key={group.label}>
                <dt className="at-caption">{group.label}</dt>
                <dd>{group.notes.map((note) => <Chip key={note} variant="note">{note}</Chip>)}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}

      {fragrance.accords.length > 0 ? (
        <section className={styles.section} aria-labelledby={`${fragrance.id}-character`}>
          <h3 id={`${fragrance.id}-character`} className={styles.heading}>Character</h3>
          <AccordStrip accords={fragrance.accords.map((entry) => ({ label: entry.name, share: entry.weight }))} />
        </section>
      ) : null}

      {layersWell}

      {owned && weekTotal > 0 ? (
        <section className={styles.section} aria-labelledby={`${fragrance.id}-wears`}>
          <h3 id={`${fragrance.id}-wears`} className={styles.heading}>Your wears <span className="at-caption">{weekTotal} in 12 weeks</span></h3>
          <div className={styles.bars} role="img" aria-label={`${weekTotal} wears in the last 12 weeks`}>
            {weeks.map((count, index) => <i key={index} style={{ height: `${Math.max(8, (count / peak) * 100)}%` }} data-on={count > 0 ? "true" : "false"} />)}
          </div>
        </section>
      ) : null}

      {variant === "page" && fragrance.similar.length > 0 ? (
        <section className={cn(styles.section, styles.wide)} aria-labelledby={`${fragrance.id}-similar`}>
          <h3 id={`${fragrance.id}-similar`} className={styles.heading}>Smells like <span className="at-caption">From the catalog</span></h3>
          <div className={styles.grid}>
            {fragrance.similar.slice(0, 10).map((similar) => (
              <FragranceCard key={similar.id} fragrance={plateFragrance(similar)} accord={accordFor(similar)} href={`/collection/${similar.id}`} />
            ))}
          </div>
        </section>
      ) : null}

      <details className={cn(styles.section, styles.about, variant === "page" && styles.wide)}>
        <summary className={styles.heading}>About this fragrance <span className="at-caption">Show <ChevronDown aria-hidden="true" /></span></summary>
        <div className={styles.aboutBody}>
          {fragrance.description ? <p>{fragrance.description}</p> : null}
          {fragrance.perfumers.length > 0 ? <p><b>Perfumers</b> {fragrance.perfumers.map((perfumer) => perfumer.name).join(", ")}</p> : null}
          {fragrance.seasons.length > 0 ? <p><b>Seasons</b> {fragrance.seasons.map((entry) => entry.season[0].toUpperCase() + entry.season.slice(1)).join(", ")}</p> : null}
          {fragrance.occasions.length > 0 ? <p><b>Occasions</b> {fragrance.occasions.map((entry) => entry.occasion[0].toUpperCase() + entry.occasion.slice(1)).join(", ")}</p> : null}
          {communityFacts.length > 0 ? <p><b>Community</b> {communityFacts.join(" · ")}</p> : null}
          {fragrance.sources.length > 0 ? (
            <p className="at-caption">
              Sources: {fragrance.sources.map((source, index) => (
                <span key={`${source.source}-${source.url ?? index}`}>{index ? ", " : ""}{source.url ? <a href={source.url} rel="noreferrer" target="_blank">{source.source}</a> : source.source}</span>
              ))}
            </p>
          ) : null}
          {fragrance.is_custom ? null : <p className="at-caption">{CATALOG_ATTRIBUTION}</p>}
        </div>
      </details>
    </article>
  );
}

export function FragranceSkeleton() {
  return (
    <div className={styles.skeleton} aria-busy="true">
      <span className="sr-only" role="status">Loading fragrance</span>
      <span className={cn("at-skeleton", styles.skeletonPlate)} />
      <span className="at-skeleton" style={{ width: 90, height: 12 }} />
      <span className="at-skeleton" style={{ width: "70%", height: 36 }} />
      <span className="at-skeleton" style={{ width: "50%", height: 14 }} />
      <span className="at-skeleton" style={{ width: 220, height: 44 }} />
    </div>
  );
}
