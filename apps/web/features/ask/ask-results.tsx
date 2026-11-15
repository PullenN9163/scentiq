"use client";

import Link from "next/link";
import { useState, useTransition } from "react";
import { toast } from "sonner";

import { Button } from "@/components/atelier/button";
import { FragranceRow } from "@/components/atelier/fragrance-row";
import { plateFragrance } from "@/components/atelier/plate-fragrance";
import { Vial } from "@/components/atelier/vial";
import type { AgentCard } from "@/features/agent/stream";
import { accordFor } from "@/lib/accord";
import { occasionLabel } from "@/lib/calendar";
import { wearRecommendation } from "@/lib/server/recommendation-actions";
import type { FragranceSummary } from "@/types/api";

import styles from "./ask.module.css";

type RecordValue = Record<string, unknown>;
function record(value: unknown): RecordValue { return value && typeof value === "object" && !Array.isArray(value) ? value as RecordValue : {}; }
function rows(value: unknown): RecordValue[] { return Array.isArray(value) ? value.map(record) : []; }
function string(value: unknown): string { return typeof value === "string" ? value : ""; }
function strings(value: unknown): string[] { return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : []; }
function number(value: unknown): number | null { return typeof value === "number" && Number.isFinite(value) ? value : null; }
function fragrance(value: unknown): FragranceSummary | null {
  const item = record(value);
  return typeof item.id === "string" && typeof item.name === "string" && typeof record(item.brand).name === "string" ? item as unknown as FragranceSummary : null;
}

function QuickWear({ recommendationId, item }: { recommendationId: string; item: RecordValue }) {
  const scent = fragrance(item.fragrance);
  const context = record(item.context);
  const [done, setDone] = useState(false);
  const [pending, startTransition] = useTransition();
  if (!scent) return null;
  function wear() {
    startTransition(async () => {
      const result = await wearRecommendation(recommendationId, {
        selected_fragrance_id: scent!.id,
        sprays: number(item.recommended_sprays),
        occasion: (string(context.occasion) || null) as never,
        setting: string(context.setting) || null,
        notes: null,
      });
      if (!result.ok) { toast.error(result.error); return; }
      setDone(true);
      toast.success("Wear logged");
    });
  }
  return <Button size="sm" variant="soft" disabled={pending || done} onClick={wear}>{done ? "Worn" : pending ? "Saving…" : "Wear it"}</Button>;
}

function recommendationCaption(item: RecordValue): string {
  const context = record(item.context);
  const date = string(context.local_date);
  const day = date ? new Date(`${date}T12:00:00Z`).toLocaleDateString("en-GB", { weekday: "short", timeZone: "UTC" }) : "";
  const occasion = string(context.occasion);
  const parts = [day, occasion ? occasionLabel(occasion as Parameters<typeof occasionLabel>[0]) : string(context.daypart) === "night" ? "Tonight" : ""].filter(Boolean);
  return parts.join(" · ");
}

/** Assistant result cards in the Atelier style. The card kinds and data guards follow result-card.tsx. */
export function AskResult({ card }: { card: AgentCard }) {
  const data = record(card.data);
  if (card.kind === "recommendation" || card.kind === "week") {
    const recommendations = Array.isArray(data.recommendations) ? rows(data.recommendations) : [data];
    const valid = recommendations.slice(0, card.kind === "week" ? 7 : 3).filter((item) => fragrance(item.fragrance) && typeof item.id === "string" && Array.isArray(item.alternatives) && item.context);
    return (
      <div className={styles.result}>
        {valid.map((item) => {
          const scent = fragrance(item.fragrance)!;
          return <FragranceRow key={string(item.id)} fragrance={plateFragrance(scent)} accord={accordFor(scent)} caption={recommendationCaption(item) || scent.brand.name} href={`/collection/${scent.id}`} trailing={<QuickWear recommendationId={string(item.id)} item={item} />} />;
        })}
        {valid.length === 0 ? <p className="at-caption">No recommendation is available from your current collection.</p> : null}
        {strings(data.gaps).length > 0 ? <p className="at-caption">{strings(data.gaps).join(" · ")}</p> : null}
        <Link className={styles.resultLink} href={card.kind === "week" ? "/week" : "/dashboard"}>{card.kind === "week" ? "Open Week" : "Open Today"}</Link>
      </div>
    );
  }
  if (card.kind === "layering") {
    const stacks = Array.isArray(card.data) ? rows(card.data) : [data];
    return (
      <div className={styles.result}>
        {stacks.slice(0, 3).map((stack, index) => {
          const items = rows(stack.items).sort((a, b) => (number(a.application_order) ?? 0) - (number(b.application_order) ?? 0));
          const members = items.map((item) => ({ item, scent: fragrance(item.fragrance) })).filter((entry): entry is { item: RecordValue; scent: FragranceSummary } => entry.scent !== null);
          const params = new URLSearchParams({ stack: members.map((entry) => entry.scent.id).join(","), mode: string(stack.mode) || "balanced" });
          if (stack.goal) params.set("goal", string(stack.goal));
          const score = number(stack.score);
          return (
            <section key={index} className={styles.stack}>
              <Vial size="sm" layers={members.map(({ item, scent }) => ({ id: scent.id, accord: accordFor(scent), sprays: number(item.suggested_sprays) ?? 1 }))} />
              <div className={styles.stackText}>
                <span className="at-card-title">{members.map((entry) => entry.scent.name).join(" + ")}</span>
                <span className="at-caption">
                  {[score !== null ? `${Math.round(score * 100)} fit` : null, string(stack.verdict) || null, members.map((entry) => `${number(entry.item.suggested_sprays) ?? 1} ${entry.scent.name}`).join(", ")].filter(Boolean).join(" · ")}
                </span>
              </div>
              <Button asChild size="sm" variant="soft"><Link href={`/layering?${params.toString()}`}>Open in Blend</Link></Button>
            </section>
          );
        })}
        {stacks.length === 0 ? <p className="at-caption">Add at least two owned fragrances to receive layering guidance.</p> : null}
        <Link className={styles.resultLink} href="/layering">Open Blend</Link>
      </div>
    );
  }
  if (card.kind === "insights") {
    const entries = Array.isArray(card.data) ? rows(card.data) : rows(data.most_worn);
    const owned = number(data.owned_items);
    const wears = number(data.total_wears);
    return (
      <div className={styles.result}>
        {!Array.isArray(card.data) && (owned !== null || wears !== null) ? (
          <p className="at-body">{[owned !== null ? `${owned} owned` : null, wears !== null ? `${wears} wears recorded` : null].filter(Boolean).join(" · ")}</p>
        ) : null}
        {entries.length > 0 ? (
          <ol className={styles.list}>
            {entries.slice(0, 5).map((entry, index) => <li key={string(entry.fragrance_id) || index}><span>{string(entry.fragrance_name)}</span><span className="at-caption">{String(entry.wear_count ?? 0)} wears</span></li>)}
          </ol>
        ) : Array.isArray(card.data) ? <p className="at-caption">There are no owned fragrances to compare yet.</p> : null}
        <Link className={styles.resultLink} href="/insights">Open Your taste</Link>
      </div>
    );
  }
  const entries = Array.isArray(card.data) ? rows(card.data) : [data];
  return (
    <div className={styles.result}>
      {entries.slice(0, 5).map((entry, index) => {
        const scent = fragrance(entry.fragrance ?? entry);
        if (scent) {
          const reason = strings(entry.reasons)[0];
          return <FragranceRow key={scent.id} fragrance={plateFragrance(scent)} accord={accordFor(scent)} caption={reason ?? scent.brand.name} href={`/collection/${scent.id}`} />;
        }
        const name = string(entry.fragrance_name);
        const when = string(entry.worn_at).slice(0, 10);
        return name ? <p key={index} className={styles.plainRow}><span>{name}</span>{when ? <span className="at-caption">{when}</span> : null}</p> : null;
      })}
      {entries.length === 0 ? <p className="at-caption">No matching results in your recorded data.</p> : null}
      <Link className={styles.resultLink} href={card.kind === "discover" ? "/discover" : "/collection"}>{card.kind === "discover" ? "Open Discover" : "Open Collection"}</Link>
    </div>
  );
}
