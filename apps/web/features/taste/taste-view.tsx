"use client";

import Link from "next/link";
import { useState } from "react";

import { stripSegments } from "@/components/atelier/accord-strip";
import { Button } from "@/components/atelier/button";
import { FragranceCard } from "@/components/atelier/fragrance-card";
import { FragranceRow } from "@/components/atelier/fragrance-row";
import { Plate, plateFragrance } from "@/components/atelier/plate";
import { Sheet } from "@/components/atelier/sheet";
import { AtelierEmpty } from "@/components/atelier/states";
import { useRegisterFragranceList } from "@/features/fragrance/fragrance-list-context";
import { WearLogSheet } from "@/features/fragrance/wear-log-sheet";
import { accordFor, accordFromLabel, accordVars } from "@/lib/accord";
import { cn } from "@/lib/utils";
import type { CollectionInsights, CollectionItem, OwnedInsightEntry } from "@/types/api";

import { AccordRing, segmentColor } from "./accord-ring";
import { byFragranceId, money, notWornLine, seasonGapSentence, sharedWords, tasteCaption, tasteStatement, thinnestSeason } from "./taste-copy";
import styles from "./taste.module.css";

const METHOD = "Each share is the share of recorded accord occurrences across the fragrances you own, not the percentage of bottles. A fragrance with several recorded accords counts toward each of them.";

/** "Your taste" (the /insights route) with the Atelier flag on. */
export function TasteView({ insights, collection }: { insights: CollectionInsights; collection: CollectionItem[] }) {
  const items = byFragranceId(collection);
  const segments = stripSegments(insights.accords);
  const [selected, setSelected] = useState(0);
  const [accordSheet, setAccordSheet] = useState<number | null>(null);
  const [methodOpen, setMethodOpen] = useState(false);
  const [wearItem, setWearItem] = useState<CollectionItem | null>(null);
  const statement = tasteStatement(insights.accords);
  const overlooked = (insights.neglected?.length ? insights.neglected : insights.least_worn ?? []).slice(0, 6);
  useRegisterFragranceList(overlooked.map((entry) => entry.fragrance_id));

  if (insights.total_items === 0) {
    return <div className="at-page"><AtelierEmpty headingLevel={1} title="Your shelf starts here" action={<Button asChild variant="outline"><Link href="/collection">Add fragrance</Link></Button>}>Add what you own and ScentIQ can describe your taste.</AtelierEmpty></div>;
  }
  if (insights.unclassified_items >= insights.total_items || segments.length === 0) {
    return (
      <div className="at-page">
        <p className="at-caption">Your taste</p>
        <AtelierEmpty headingLevel={1} title="ScentIQ needs a few more details about your fragrances." action={<Link className="at-link" href="/collection">Open Collection</Link>}>Fragrances with recorded accords appear here as your taste profile.</AtelierEmpty>
      </div>
    );
  }

  const owned = collection.filter((item) => item.status === "owned");
  const sheetSegment = accordSheet !== null ? segments[accordSheet] : null;
  const topKeys = new Set(segments.filter((segment) => segment.key !== "other").map((segment) => segment.key));
  const sheetItems = sheetSegment ? owned.filter((item) => (sheetSegment.key === "other" ? !topKeys.has(accordFor(item.fragrance)) : accordFor(item.fragrance) === sheetSegment.key)) : [];
  const noWears = insights.total_wears === 0;
  const peak = Math.max(1, ...insights.most_worn.map((entry) => entry.wear_count));
  const thin = thinnestSeason(insights.seasons);
  const gaps = seasonGapSentence(insights.season_gaps);
  const pairs = (insights.redundancy_pairs ?? []).slice(0, 2);
  const costs = insights.priced_items > 0 ? (insights.cost_per_wear ?? []).filter((entry) => entry.cost_per_wear) : [];

  return (
    <div className="at-page">
      <p className="at-caption">Your taste</p>
      <h1 className={styles.statement}>{statement}</h1>
      <p className="at-caption">{tasteCaption(insights)}</p>

      <div className={styles.top}>
        <section className={styles.profile} aria-label="Accord profile">
          <AccordRing segments={segments} selected={selected} />
          <div className={styles.legendBlock}>
            <ul className={styles.legend}>
              {segments.map((segment, index) => (
                <li key={segment.label}>
                  <button
                    type="button"
                    className={cn(styles.legendRow, index === selected && styles.legendSelected)}
                    aria-pressed={index === selected}
                    onClick={() => { setSelected(index); setAccordSheet(index); }}
                  >
                    <i style={{ background: segmentColor(segment.key) }} aria-hidden="true" />
                    <span>{segment.label}</span>{" "}
                    <span className="at-tabular">{Math.round(segment.share * 100)}%</span>
                  </button>
                </li>
              ))}
            </ul>
            <Button size="sm" variant="text" className={styles.method} onClick={() => setMethodOpen(true)}>How this is counted</Button>
          </div>
        </section>

        {noWears ? (
          <p className={cn("at-caption", styles.noWears)}>Wear a few fragrances and your habits appear here.</p>
        ) : insights.most_worn.length > 0 ? (
          <section aria-labelledby="reach-for" className={styles.reach}>
            <h2 id="reach-for" className="at-title">What you reach for</h2>
            <ol className={styles.ranked}>
              {insights.most_worn.slice(0, 4).map((entry) => {
                const item = items.get(entry.fragrance_id);
                const accord = item ? accordFor(item.fragrance) : "neutral";
                return (
                  <li key={entry.collection_item_id}>
                    <Link href={`/collection/${entry.fragrance_id}`} className="at-card-title">{entry.fragrance_name}</Link>
                    <span className={styles.bar} style={accordVars(accord)}><i style={{ width: `${(entry.wear_count / peak) * 100}%` }} /></span>
                    <span className="at-caption at-tabular">{entry.wear_count}</span>
                  </li>
                );
              })}
            </ol>
          </section>
        ) : null}
      </div>

      {!noWears && overlooked.length > 0 ? (
        <section className={styles.section} aria-labelledby="overlooked">
          <div className={styles.sectionHead}><h2 id="overlooked" className={styles.subhead}>Overlooked</h2></div>
          <ul className={styles.strip}>
            {overlooked.map((entry: OwnedInsightEntry) => {
              const item = items.get(entry.fragrance_id);
              const fragrance = item?.fragrance;
              return (
                <li key={entry.collection_item_id}>
                  <FragranceCard
                    fragrance={fragrance ? plateFragrance(fragrance) : { id: entry.fragrance_id, name: entry.fragrance_name, brand: entry.brand_name, imageUrl: null }}
                    accord={fragrance ? accordFor(fragrance) : "neutral"}
                    href={`/collection/${entry.fragrance_id}`}
                    caption={notWornLine(entry.last_worn_at)}
                    actions={item ? [{ label: "Wear it", onSelect: () => setWearItem(item) }] : []}
                  />
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      {!noWears && insights.seasons.length > 0 ? (
        <section className={styles.section} aria-labelledby="seasons">
          <div className={styles.sectionHead}><h2 id="seasons" className={styles.subhead}>Season coverage</h2></div>
          <dl className={styles.seasons}>
            {insights.seasons.map((season) => (
              <div key={season.label} className={cn(season.label === thin && styles.thin)}>
                <dt>{season.label}{season.label === thin ? <span> · thin</span> : null}</dt>
                <dd className="at-numeral">{season.count}</dd>
              </div>
            ))}
          </dl>
          {gaps ? <p className="at-caption">{gaps}</p> : null}
        </section>
      ) : null}

      {!noWears && (pairs.length > 0 || costs.length > 0) ? (
        <div className={styles.pair}>
          {pairs.length > 0 ? (
            <section aria-labelledby="alike">
              <h2 id="alike" className={styles.subhead}>These two smell alike</h2>
              {pairs.map((pair) => {
                const first = items.get(pair.first_id)?.fragrance;
                const second = items.get(pair.second_id)?.fragrance;
                return (
                  <div key={`${pair.first_id}-${pair.second_id}`} className={styles.alike}>
                    <span className={styles.alikePlates} aria-hidden="true">
                      <Plate fragrance={first ? plateFragrance(first) : { id: pair.first_id, name: pair.first_name, brand: "", imageUrl: null }} accord={first ? accordFor(first) : "neutral"} className={styles.mini} compact decorative />
                      <Plate fragrance={second ? plateFragrance(second) : { id: pair.second_id, name: pair.second_name, brand: "", imageUrl: null }} accord={second ? accordFor(second) : "neutral"} className={styles.mini} compact decorative />
                    </span>
                    <span className={styles.alikeText}>
                      <b className="at-card-title">{pair.first_name}</b>
                      <span className="at-caption">and {pair.second_name} {sharedWords(pair.shared_accords)}</span>
                    </span>
                    <span className="at-caption at-tabular">{Math.round(pair.overlap * 100)}% overlap</span>
                  </div>
                );
              })}
            </section>
          ) : null}
          {costs.length > 0 ? (
            <section aria-labelledby="cost">
              <div className={styles.sectionHead}><h2 id="cost" className={styles.subhead}>Cost per wear</h2><span className="at-caption">Priced bottles only</span></div>
              {costs.slice(0, 4).map((entry) => {
                const item = items.get(entry.fragrance_id);
                const price = money(item?.purchase_price);
                return (
                  <FragranceRow
                    key={entry.collection_item_id}
                    className={styles.costRow}
                    fragrance={item ? plateFragrance(item.fragrance) : { id: entry.fragrance_id, name: entry.fragrance_name, brand: entry.brand_name, imageUrl: null }}
                    accord={item ? accordFor(item.fragrance) : accordFromLabel(null)}
                    caption={[price, `${entry.wear_count} ${entry.wear_count === 1 ? "wear" : "wears"}`].filter(Boolean).join(" · ")}
                    href={`/collection/${entry.fragrance_id}`}
                    trailing={<span className="at-tabular">{money(entry.cost_per_wear)} a wear</span>}
                  />
                );
              })}
            </section>
          ) : null}
        </div>
      ) : null}

      <Sheet open={sheetSegment !== null} onOpenChange={(open) => { if (!open) setAccordSheet(null); }} title={sheetSegment ? `${sheetSegment.label} on your shelf` : "Accord"}>
        {sheetItems.length > 0 ? (
          <div className={styles.sheetList}>
            {sheetItems.map((item) => <FragranceRow key={item.id} fragrance={plateFragrance(item.fragrance)} accord={accordFor(item.fragrance)} caption={item.fragrance.brand.name} href={`/collection/${item.fragrance.id}`} className={styles.costRow} />)}
          </div>
        ) : <p className="at-caption">No owned fragrance leads with this accord.</p>}
      </Sheet>
      <Sheet open={methodOpen} onOpenChange={setMethodOpen} title="How this is counted"><p className="at-body">{METHOD}</p></Sheet>
      {wearItem ? <WearLogSheet itemId={wearItem.id} fragranceName={wearItem.fragrance.name} open onOpenChange={(open) => { if (!open) setWearItem(null); }} /> : null}
    </div>
  );
}

export function TasteSkeleton() {
  return (
    <div className="at-page" aria-busy="true">
      <span className="sr-only" role="status">Reading your taste</span>
      <span className="at-skeleton" style={{ width: "60%", height: 56, marginBottom: 24 }} />
      <div className={styles.top}>
        <span className="at-skeleton" style={{ width: 240, height: 240, borderRadius: "50%" }} />
        <div style={{ display: "grid", gap: 12 }}>{[0, 1, 2, 3].map((index) => <span key={index} className="at-skeleton" style={{ height: 36 }} />)}</div>
      </div>
    </div>
  );
}
