"use client";

import Link from "next/link";
import { CatalogImage } from "@/components/catalog-image";
import { Badge } from "@/components/ui/badge";
import { RecommendationCard } from "@/features/recommendations/recommendation-card";
import type { FragranceSummary } from "@/types/api";
import type { WearRecommendation } from "@/types/wear-intelligence";
import type { AgentCard } from "./stream";

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

function FragrancePreview({ item }: { item: FragranceSummary }) {
  return <><CatalogImage id={item.id} name={item.name} brand={item.brand.name} imageUrl={item.image_url} className="agent-stack-image" /><strong>{item.name}</strong><p className="muted">{item.brand.name}</p></>;
}

export function AgentResultCard({ card }: { card: AgentCard }) {
  const data = record(card.data);
  if (card.kind === "recommendation" || card.kind === "week") {
    const recommendations = Array.isArray(data.recommendations) ? rows(data.recommendations) : [data];
    return <div className="agent-result">
      {recommendations.slice(0, card.kind === "week" ? 7 : 3).map((item) => fragrance(item.fragrance) && typeof item.id === "string" && Array.isArray(item.alternatives) && item.context ? <RecommendationCard key={string(item.id)} recommendation={item as unknown as WearRecommendation} compact /> : null)}
      {recommendations.length === 0 && <p>No recommendation is available from your current collection.</p>}
      {strings(data.gaps).length > 0 && <p className="muted">{strings(data.gaps).join(" · ")}</p>}
      <Link href={card.kind === "week" ? "/week" : "/dashboard"}>{card.kind === "week" ? "Open My Week" : "Open Today"}</Link>
    </div>;
  }
  if (card.kind === "layering") {
    const stacks = Array.isArray(card.data) ? rows(card.data) : [data];
    return <div className="agent-result">
      {stacks.slice(0, 3).map((stack, index) => {
        const items = rows(stack.items);
        const ids = items.map((item) => string(record(item.fragrance).id)).filter(Boolean);
        const params = new URLSearchParams({ stack: ids.join(","), mode: string(stack.mode) || "balanced" });
        if (stack.goal) params.set("goal", string(stack.goal));
        return <section key={index}>
          <h3>Owned layering stack {number(stack.score) !== null && <Badge>{Math.round((number(stack.score) ?? 0) * 100)}% match</Badge>}</h3>
          <div className="agent-result-grid">{items.sort((a, b) => (number(a.application_order) ?? 0) - (number(b.application_order) ?? 0)).map((item) => {
            const scent = fragrance(item.fragrance);
            return scent ? <div className="agent-stack-member" key={scent.id} data-anchor={item.role === "anchor"}><FragrancePreview item={scent} /><Badge>{string(item.role)}</Badge><p>{String(item.application_order)}. Apply {String(item.suggested_sprays)} spray(s)</p></div> : null;
          })}</div>
          <ul>{strings(stack.reasons).slice(0, 3).map((reason) => <li key={reason}>{reason}</li>)}</ul>
          {strings(stack.warnings).map((warning) => <p className="muted" key={warning}>{warning}</p>)}
          <p className="muted">{string(stack.evidence_label)} evidence · Spray split is starting guidance.</p>
          <Link href={`/layering?${params.toString()}`}>Open stack in Layering Lab</Link>
        </section>;
      })}
      {stacks.length === 0 && <p>Add at least two owned fragrances to receive layering guidance.</p>}
    </div>;
  }
  if (card.kind === "insights") {
    const entries = Array.isArray(card.data) ? rows(card.data) : rows(data.most_worn);
    return <div className="agent-result"><h3>Your collection evidence</h3>
      {!Array.isArray(card.data) && <dl className="agent-metrics"><div><dt>Owned bottles</dt><dd>{number(data.owned_items) ?? "—"}</dd></div><div><dt>Recorded wears</dt><dd>{number(data.total_wears) ?? "—"}</dd></div><div><dt>Recorded purchase value</dt><dd>{string(data.total_purchase_value) || "Not recorded"}</dd></div></dl>}
      <ul>{entries.slice(0, 5).map((entry, index) => <li key={string(entry.fragrance_id) || index}>{string(entry.fragrance_name)} · {String(entry.wear_count ?? 0)} recorded wears</li>)}</ul>
      {Array.isArray(card.data) && !entries.length && <p>There are no owned fragrances to compare yet.</p>}
      <Link href="/insights">Open Insights</Link></div>;
  }
  const entries = Array.isArray(card.data) ? rows(card.data) : [data];
  return <div className="agent-result"><h3>{card.kind === "discover" ? "Catalog suggestions" : card.kind === "wears" ? "Recent wears" : "Fragrance evidence"}</h3>
    {entries.slice(0, 5).map((entry, index) => {
      const scent = fragrance(entry.fragrance ?? entry);
      return <div key={scent?.id ?? index}>{scent ? <><FragrancePreview item={scent} />{number(entry.score) !== null && <p>Deterministic score: {Math.round((number(entry.score) ?? 0) * 100)}%</p>}<ul>{strings(entry.reasons).slice(0, 2).map((reason) => <li key={reason}>{reason}</li>)}</ul><Link href={`/collection/${scent.id}`}>Fragrance details</Link></> : <p>{string(entry.fragrance_name)} {string(entry.worn_at).slice(0, 10)}</p>}</div>;
    })}
    {entries.length === 0 && <p>No matching results in your recorded data.</p>}
    <Link href={card.kind === "discover" ? "/discover" : "/collection"}>{card.kind === "discover" ? "Open Discover" : "Open collection"}</Link>
  </div>;
}
