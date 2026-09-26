"use client";

import { Sparkles } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState, useTransition } from "react";

import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { getLayeringPair } from "@/lib/server/actions";
import type { FragranceSummary, LayeringMode, LayeringSuggestion } from "@/types/api";

const modes: LayeringMode[] = ["safe", "contrast", "experimental"];

export function LayeringLab({ owned, suggestions, initialA }: { owned: FragranceSummary[]; suggestions: LayeringSuggestion[]; initialA?: string }) {
  const initial = suggestions.find((item) => item.first.id === initialA || item.second.id === initialA) ?? suggestions[0];
  const [mode, setMode] = useState<LayeringMode>(initial?.mode ?? "safe");
  const [firstId, setFirstId] = useState(initial?.first.id ?? owned[0]?.id ?? "");
  const [secondId, setSecondId] = useState(initial?.second.id ?? owned[1]?.id ?? "");
  const [remote, setRemote] = useState<{ key: string; value: LayeringSuggestion | null } | null>(null);
  const [isScoring, startScoring] = useTransition();
  const key = `${mode}:${firstId}:${secondId}`;
  const loaded = useMemo(() => suggestions.find((item) => item.mode === mode && new Set([item.first.id, item.second.id]).has(firstId) && new Set([item.first.id, item.second.id]).has(secondId) && firstId !== secondId), [suggestions, mode, firstId, secondId]);
  useEffect(() => {
    if (loaded || !firstId || !secondId || firstId === secondId) return;
    let active = true;
    startScoring(async () => {
      const value = await getLayeringPair(firstId, secondId, mode);
      if (active) setRemote({ key, value });
    });
    return () => { active = false; };
  }, [firstId, key, loaded, mode, secondId]);
  const suggestion = loaded ?? (remote?.key === key ? remote.value : null);

  if (owned.length < 2) {
    return <section className="page"><PageHeader eyebrow="Pair with intention" title="Layering Lab" description="Guidance from fragrances you own." /><Card><CardContent className="empty-panel"><h2>Add at least two owned fragrances</h2><p>Layering suggestions never use wishlist, sold, or fictional catalog entries.</p><Button asChild><Link href="/collection">Open collection</Link></Button></CardContent></Card></section>;
  }
  return (
    <section className="page">
      <PageHeader eyebrow="Pair with intention" title="Layering Lab" description="Deterministic guidance from fragrances in your collection." />
      <p className="data-note">Guidance reflects catalog overlap, not chemistry or skin safety.</p>
      <Card><CardContent><div className="layer-selectors"><label>Fragrance A<select className="select" value={firstId} onChange={(event) => setFirstId(event.target.value)}>{owned.map((item) => <option key={item.id} value={item.id} disabled={item.id === secondId}>{item.name}</option>)}</select></label><label>Fragrance B<select className="select" value={secondId} onChange={(event) => setSecondId(event.target.value)}>{owned.map((item) => <option key={item.id} value={item.id} disabled={item.id === firstId}>{item.name}</option>)}</select></label></div><div className="mode-tabs">{modes.map((item) => <Button key={item} variant={mode === item ? "primary" : "secondary"} onClick={() => setMode(item)}>{item}</Button>)}</div></CardContent></Card>
      {suggestion ? <Card className="layer-result"><CardContent><Badge>{suggestion.mode}</Badge><h2 className="serif">{suggestion.first.name} + {suggestion.second.name}</h2><Progress value={suggestion.score * 100} label="Compatibility score" /><div className="result-grid"><div><span>Shared notes</span><strong>{suggestion.shared_notes.join(", ") || "None recorded"}</strong></div><div><span>Complementary accords</span><strong>{suggestion.complementary_accords.join(", ") || "None recorded"}</strong></div><div><span>Season overlap</span><strong>{Math.round(suggestion.season_overlap * 100)}%</strong></div></div></CardContent></Card> : <Card><CardContent className="empty-panel"><Sparkles /><h2>{isScoring ? "Scoring this pairing…" : "No supported pairing for this selection"}</h2><p>{isScoring ? "Using recorded notes, accords, and seasons." : "Choose one of the scored pairs below."}</p></CardContent></Card>}
      <div className="suggestion-section"><h2>Suggested combinations</h2><div className="grid grid-3">{suggestions.map((item) => <button className="pair-card" key={`${item.mode}-${item.first.id}-${item.second.id}`} onClick={() => { setMode(item.mode); setFirstId(item.first.id); setSecondId(item.second.id); }}><Badge>{item.mode}</Badge><strong>{item.first.name} + {item.second.name}</strong><span>{Math.round(item.score * 100)}% compatibility</span></button>)}</div></div>
    </section>
  );
}
