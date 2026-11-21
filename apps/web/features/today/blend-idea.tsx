import Link from "next/link";

import { accordFor, accordVars } from "@/lib/accord";
import type { LayeringStackSuggestion } from "@/types/layering";

/** Where a blend opens in the Blend Studio. */
export function blendHref(blend: LayeringStackSuggestion): string {
  return `/layering?stack=${blend.items.map((item) => item.fragrance.id).join(",")}&mode=${blend.mode}${blend.goal ? `&goal=${blend.goal}` : ""}`;
}

/** One line a day: the researched blend for the pick, with its match, sprays and where to spray. */
export function blendSummary(blend: LayeringStackSuggestion): string {
  const places = blend.items
    .map((item) => `${item.fragrance.name} on ${(item.zones ?? []).map((zone) => zone.zone.replaceAll("_", " ")).join(" and ") || "skin"}`)
    .join("; ");
  return `${blend.score_percent}% match · ${blend.total_sprays} sprays · ${places}`;
}

export function BlendIdea({ blend, className }: { blend: LayeringStackSuggestion; className?: string }) {
  return (
    <Link className={className} href={blendHref(blend)}>
      <span aria-hidden="true">
        {blend.items.map((item) => <i key={item.fragrance.id} style={{ ...accordVars(accordFor(item.fragrance)), display: "inline-block", width: 10, height: 10, borderRadius: "50%", marginRight: 4, background: "var(--af)" }} />)}
      </span>
      <b>{`Blend ${blend.items.map((item) => item.fragrance.name).join(" + ")}`}</b>
      <span className="at-caption"> {blendSummary(blend)}</span>
    </Link>
  );
}
