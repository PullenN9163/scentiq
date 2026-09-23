"use client";

import { ArrowDownUp, Bookmark, RefreshCw, Sparkles } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { fragrances, getDemoFragranceById, getDemoLayeringSuggestions } from "@/lib/demo";

const modes = ["Safe", "Contrast", "Experimental"] as const;
type Mode = (typeof modes)[number];

export function LayeringLab({ initialA }: { initialA?: string }) {
  const suggestions = getDemoLayeringSuggestions();
  const initialSuggestion = suggestions.find((item) => initialA && [item.fragranceAId, item.fragranceBId].includes(initialA)) ?? suggestions[0];
  const [a, setA] = useState(initialA && getDemoFragranceById(initialA) ? initialA : initialSuggestion.fragranceAId);
  const [b, setB] = useState(initialA === initialSuggestion.fragranceBId ? initialSuggestion.fragranceAId : initialSuggestion.fragranceBId);
  const [mode, setMode] = useState<Mode>(initialSuggestion.mode);
  const [saved, setSaved] = useState(false);
  const suggestion = suggestions.find((item) => item.mode === mode && [item.fragranceAId, item.fragranceBId].includes(a) && [item.fragranceAId, item.fragranceBId].includes(b) && a !== b);
  const scentA = getDemoFragranceById(a)!;
  const scentB = getDemoFragranceById(b)!;
  const score = suggestion ? Math.max(62, Math.min(96, suggestion.score + (mode === "Safe" ? 3 : mode === "Experimental" ? -7 : 0))) : 0;
  const chooseSuggestion = (next: (typeof suggestions)[number]) => { setA(next.fragranceAId); setB(next.fragranceBId); setMode(next.mode); setSaved(false); };
  const tryAnother = () => { const index = suggestion ? suggestions.findIndex((item) => item.id === suggestion.id) : -1; chooseSuggestion(suggestions[(index + 1) % suggestions.length]); };
  return (
    <section className="page">
      <PageHeader eyebrow="Pair with intention" title="Layering Lab" description="Deterministic demo guidance for combining fragrances you own." />
      <div className="layer-builder">
        <Card><CardContent><div className="layer-selectors"><label><span>Fragrance A</span><select className="select" aria-label="Fragrance A" value={a} onChange={(event) => { setA(event.target.value); setSaved(false); }}>{fragrances.map((item) => <option value={item.id} key={item.id} disabled={item.id === b}>{item.name}</option>)}</select></label><Button size="icon" variant="secondary" aria-label="Swap fragrances" onClick={() => { setA(b); setB(a); }}><ArrowDownUp size={18} /></Button><label><span>Fragrance B</span><select className="select" aria-label="Fragrance B" value={b} onChange={(event) => { setB(event.target.value); setSaved(false); }}>{fragrances.map((item) => <option value={item.id} key={item.id} disabled={item.id === a}>{item.name}</option>)}</select></label></div><div className="mode-tabs" aria-label="Layering mode">{modes.map((item) => <Button key={item} variant={mode === item ? "primary" : "secondary"} onClick={() => { const next = suggestions.find((entry) => entry.mode === item)!; chooseSuggestion(next); }}>{item}</Button>)}</div></CardContent></Card>
        <Card className="layer-result"><CardContent><div className="layer-result__heading"><div><p className="eyebrow">{mode} guidance</p><h2 className="serif">{scentA.name} <span>+</span> {scentB.name}</h2></div>{suggestion && <strong>{score}<small>/100</small></strong>}</div>{suggestion ? <><Progress value={score} label="Compatibility score" /><p className="guidance-note">This is taste guidance from demo data, not a prediction of chemical behavior on skin.</p><div className="result-grid"><div><span>Shared notes</span><strong>{suggestion.sharedNotes.join(", ") || "Texture and warmth"}</strong></div><div><span>Complementary accords</span><strong>{suggestion.complements.join(", ")}</strong></div><div><span>Potential clashes</span><strong>{suggestion.clashes.join(", ") || "None flagged"}</strong></div><div><span>Season overlap</span><strong>{suggestion.seasons.join(", ")}</strong></div><div><span>Occasion overlap</span><strong>{suggestion.occasions.join(", ")}</strong></div><div><span>Best occasions</span><strong>{suggestion.occasions.join(", ")}</strong></div><div><span>Application order</span><strong>{suggestion.order}</strong></div><div><span>Spray ratio</span><strong>{suggestion.ratio}</strong></div></div><p>{suggestion.explanation}</p><div className="cluster"><Button onClick={() => setSaved(true)}><Bookmark size={17} />Save combination</Button><Button variant="secondary" onClick={tryAnother}><RefreshCw size={17} />Try another pair</Button></div>{saved && <p className="success-note" role="status">Combination saved for this demo session.</p>}</> : <div className="empty-panel"><h3>No curated {mode.toLowerCase()} pairing for this combination</h3><p>Choose a suggested pair or try another mode. ScentIQ will not invent guidance for an unsupported demo pairing.</p><Button variant="secondary" onClick={tryAnother}>Show a curated pair</Button></div>}</CardContent></Card>
      </div>
      <div className="suggestion-section"><div className="section-title"><Sparkles size={19} /><h2>Suggested combinations</h2></div><div className="grid grid-3">{suggestions.slice(0, 3).map((item) => { const first = getDemoFragranceById(item.fragranceAId)!; const second = getDemoFragranceById(item.fragranceBId)!; return <button className="pair-card" key={item.id} onClick={() => chooseSuggestion(item)}><Badge>{item.mode}</Badge><strong>{first.name} + {second.name}</strong><span>{item.score}% demo compatibility</span></button>; })}</div><p className="muted">Recently tried in this demo: Cedar After Rain + Linen & Neroli · Fig Circuit + Amber Index</p></div>
    </section>
  );
}
