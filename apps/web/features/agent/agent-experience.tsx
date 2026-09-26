"use client";

import { ArrowRight, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PageHeader } from "@/components/shared/page-header";
import { PreviewNotice } from "@/components/shared/states";
import { Badge } from "@/components/ui/badge";
import { rankFragrances, seasonForMonth } from "@/lib/catalog-ranking";
import type { CollectionInsights, FragranceDetail, LayeringSuggestion } from "@/types/api";

const prompts = ["What should I wear today?", "What is my most worn fragrance?", "What can I layer?"] as const;

export function AgentExperience({ owned, insights, layering }: { owned: FragranceDetail[]; insights: CollectionInsights; layering: LayeringSuggestion[] }) {
  const [answer, setAnswer] = useState<string | null>(null);
  function ask(prompt: (typeof prompts)[number]) {
    if (owned.length === 0) { setAnswer("Your owned collection is empty. Add a fragrance before asking for a collection-based answer."); return; }
    if (prompt === prompts[0]) { const now = new Date(); const best = rankFragrances(owned, { season: seasonForMonth(now.getMonth()), daypart: now.getHours() >= 17 ? "night" : "day", coolWeather: now.getMonth() < 2 || now.getMonth() > 9 })[0]; setAnswer(`${best.name} is the strongest catalog-supported match in your collection for the current season and daypart.`); return; }
    if (prompt === prompts[1]) { const most = insights.most_worn[0]; setAnswer(most ? `${most.fragrance_name} leads your wear history with ${most.wear_count} wears.` : "You have not logged a wear yet."); return; }
    const pair = layering[0]; setAnswer(pair ? `${pair.first.name} + ${pair.second.name} is your highest-ranked ${pair.mode} pairing.` : "Add at least two owned fragrances to receive layering guidance.");
  }
  return <section className="page agent-page"><PageHeader eyebrow="Collection advisor" title="Ask ScentIQ" description="Deterministic answers grounded in your persisted collection and insights." /><PreviewNotice>Weather and calendar context remains a preview. Answers use only supported intents and your real collection.</PreviewNotice><div className="agent-shell"><div className="conversation" aria-live="polite">{answer ? <div className="agent-bubble"><Badge>Collection answer</Badge><p>{answer}</p><Link href="/collection">Open collection <ArrowRight size={15} /></Link></div> : <div className="agent-welcome"><Sparkles /><h2 className="serif">What would you like to decide?</h2></div>}</div><div className="quick-prompts">{prompts.map((prompt) => <button key={prompt} onClick={() => ask(prompt)}>{prompt}</button>)}</div></div></section>;
}
