"use client";

import { BookmarkPlus, Compass, SlidersHorizontal } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { fragrances } from "@/lib/demo";

const modes = ["Balance My Collection", "More of What I Love", "Challenge My Taste", "Seasonal Purchase", "Office", "Date Night"];

export function DiscoverExperience() {
  const [mode, setMode] = useState(modes[0]);
  const [budget, setBudget] = useState("250");
  const [season, setSeason] = useState("All");
  const [wishlisted, setWishlisted] = useState<string[]>([]);
  const candidates = fragrances.slice(9).filter((item) => (item.demoPrice ?? 0) <= Number(budget) && (season === "All" || item.seasons.includes(season as never)));
  return (
    <section className="page">
      <PageHeader eyebrow="Beyond the shelf" title="Discover" description="Curated demo recommendations that expand your collection instead of repeating it." />
      <div className="discover-modes" aria-label="Discovery modes">{modes.map((item) => <Button key={item} size="sm" variant={mode === item ? "primary" : "secondary"} onClick={() => setMode(item)}>{item}</Button>)}</div>
      <Card className="discover-intro"><CardContent><Compass size={24} /><div><p className="eyebrow">{mode}</p><h2 className="serif">{mode === "Challenge My Taste" ? "Challenge mode: one step beyond familiar." : "A considered next move."}</h2><p>{mode === "Challenge My Taste" ? "These picks introduce a new texture or family while preserving a thread of your existing taste." : "Candidates are ranked against demo taste, use-case coverage, and redundancy."}</p></div></CardContent></Card>
      <div className="discover-filters"><SlidersHorizontal size={18} /><label>Budget<select className="select" aria-label="Budget" value={budget} onChange={(event) => setBudget(event.target.value)}><option value="100">Up to $100</option><option value="150">Up to $150</option><option value="250">Up to $250</option></select></label><label>Season<select className="select" aria-label="Season" value={season} onChange={(event) => setSeason(event.target.value)}><option>All</option><option>Spring</option><option>Summer</option><option>Fall</option><option>Winter</option></select></label><label>Redundancy<select className="select" aria-label="Redundancy tolerance"><option>Low</option><option>Medium</option><option>High</option></select></label></div>
      <div className="discover-grid">{candidates.map((item, index) => { const saved = wishlisted.includes(item.id); return <Card key={item.id} className="discovery-card" data-testid="discovery-card"><div className="discovery-card__art" style={{ "--scent-tone": item.tone } as React.CSSProperties}><Badge>{mode}</Badge><span>{item.brand}</span></div><CardContent><p className="eyebrow">{item.family} · Demo catalog</p><h2 className="serif">{item.name}</h2><p>{item.description}</p><dl className="score-list"><div><dt>Taste match</dt><dd>{89 - index * 3}%</dd></div><div><dt>Collection expansion</dt><dd>{92 - index * 4}%</dd></div><div><dt>Redundancy risk</dt><dd>{18 + index * 5}%</dd></div></dl><p><strong>${item.demoPrice}</strong> <small>illustrative price</small></p><Button disabled={saved} variant={saved ? "secondary" : "primary"} onClick={() => setWishlisted((items) => [...items, item.id])}><BookmarkPlus size={16} />{saved ? "Wishlisted" : "Add to wishlist"}</Button></CardContent></Card>; })}</div>
      <Card className="upcoming"><CardContent><Badge>Curated demo</Badge><h2 className="serif">On the horizon</h2><p>Editorial placeholders for future releases—never presented as live or current retailer data.</p><div className="cluster"><span>Mineral Iris · October study</span><span>Green Suede · Winter study</span></div></CardContent></Card>
    </section>
  );
}
