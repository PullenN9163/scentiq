"use client";

import { BookmarkPlus, Compass, SlidersHorizontal } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/shared/page-header";
import { PreviewNotice } from "@/components/shared/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { fragrances } from "@/lib/demo";

const modes = ["Balance My Collection", "More of What I Love", "Challenge My Taste", "Seasonal Purchase", "Office", "Date Night"];

export function DiscoverExperience() {
  const [mode, setMode] = useState(modes[0]);
  const [budget, setBudget] = useState("250");
  const [season, setSeason] = useState("All");
  const [occasion, setOccasion] = useState("All");
  const [family, setFamily] = useState("All");
  const [redundancy, setRedundancy] = useState("Medium");
  const [wishlisted, setWishlisted] = useState<string[]>([]);
  const catalog = fragrances.slice(9).map((item, index) => ({ item, taste: 89 - index * 3, expansion: 92 - index * 4, risk: 18 + index * 5 }));
  const modeMatch = (item: (typeof fragrances)[number]) => mode === "Office" ? item.occasions.includes("Office") : mode === "Date Night" ? item.occasions.includes("Date") : mode === "Seasonal Purchase" ? item.seasons.includes(season === "All" ? "Fall" : season as never) : mode === "Challenge My Taste" ? ["Leather", "Fresh", "Fruity"].includes(item.family) : mode === "More of What I Love" ? item.accords.some((accord) => ["woody", "clean", "musky"].includes(accord)) : true;
  const riskLimit = redundancy === "Low" ? 24 : redundancy === "Medium" ? 34 : 100;
  const candidates = catalog.filter(({ item, risk }) => (item.demoPrice ?? 0) <= Number(budget) && (season === "All" || item.seasons.includes(season as never)) && (occasion === "All" || item.occasions.includes(occasion as never)) && (family === "All" || item.family === family) && risk <= riskLimit && modeMatch(item));
  return (
    <section className="page">
      <PageHeader eyebrow="Beyond the shelf" title="Discover" description="Curated demo recommendations that expand your collection instead of repeating it." />
      <PreviewNotice>Discovery is a preview built on sample data. Wishlisting here is not saved to your account.</PreviewNotice>
      <div className="discover-modes" aria-label="Discovery modes">{modes.map((item) => <Button key={item} size="sm" variant={mode === item ? "primary" : "secondary"} onClick={() => setMode(item)}>{item}</Button>)}</div>
      <Card className="discover-intro"><CardContent><Compass size={24} /><div><p className="eyebrow">{mode}</p><h2 className="serif">{mode === "Challenge My Taste" ? "Challenge mode: one step beyond familiar." : "A considered next move."}</h2><p>{mode === "Challenge My Taste" ? "These picks introduce a new texture or family while preserving a thread of your existing taste." : "Candidates are ranked against demo taste, use-case coverage, and redundancy."}</p></div></CardContent></Card>
      <div className="discover-filters"><SlidersHorizontal size={18} /><label>Budget<select className="select" aria-label="Budget" value={budget} onChange={(event) => setBudget(event.target.value)}><option value="100">Up to $100</option><option value="150">Up to $150</option><option value="250">Up to $250</option></select></label><label>Season<select className="select" aria-label="Season" value={season} onChange={(event) => setSeason(event.target.value)}><option>All</option><option>Spring</option><option>Summer</option><option>Fall</option><option>Winter</option></select></label><label>Occasion<select className="select" aria-label="Occasion" value={occasion} onChange={(event) => setOccasion(event.target.value)}><option>All</option><option>Office</option><option>Date</option><option>Formal</option><option>Gym</option><option>Travel</option></select></label><label>Family<select className="select" aria-label="Fragrance family" value={family} onChange={(event) => setFamily(event.target.value)}><option>All</option>{[...new Set(catalog.map(({ item }) => item.family))].map((value) => <option key={value}>{value}</option>)}</select></label><label>Redundancy<select className="select" aria-label="Redundancy tolerance" value={redundancy} onChange={(event) => setRedundancy(event.target.value)}><option>Low</option><option>Medium</option><option>High</option></select></label></div>
      {candidates.length ? <div className="discover-grid">{candidates.map(({ item, taste, expansion, risk }) => { const saved = wishlisted.includes(item.id); return <Card key={item.id} className="discovery-card" data-testid="discovery-card"><div className="discovery-card__art" style={{ "--scent-tone": item.tone } as React.CSSProperties}><Badge>{mode}</Badge><span>{item.brand}</span></div><CardContent><p className="eyebrow">{item.family} · Demo catalog</p><h2 className="serif">{item.name}</h2><p>{item.description}</p><dl className="score-list"><div><dt>Taste match</dt><dd>{taste}%</dd></div><div><dt>Collection expansion</dt><dd>{expansion}%</dd></div><div><dt>Redundancy risk</dt><dd>{risk}%</dd></div></dl><p><strong>${item.demoPrice}</strong> <small>illustrative price</small></p><Button disabled={saved} variant={saved ? "secondary" : "primary"} onClick={() => setWishlisted((items) => [...items, item.id])}><BookmarkPlus size={16} />{saved ? "Marked in preview" : "Mark in preview"}</Button></CardContent></Card>; })}</div> : <Card><CardContent className="empty-panel"><h2>No demo matches</h2><p>Broaden a filter or choose another discovery mode.</p><Button variant="secondary" onClick={() => { setBudget("250"); setSeason("All"); setOccasion("All"); setFamily("All"); setRedundancy("High"); setMode(modes[0]); }}>Reset discovery</Button></CardContent></Card>}
      <Card className="upcoming"><CardContent><Badge>Curated demo</Badge><h2 className="serif">On the horizon</h2><p>Editorial placeholders for future releases—never presented as live or current retailer data.</p><div className="cluster"><span>Mineral Iris · October study</span><span>Green Suede · Winter study</span></div></CardContent></Card>
    </section>
  );
}
