"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { getDemoFragranceById, getDemoInsights } from "@/lib/demo";

export function CollectionInsights() {
  const insights = getDemoInsights();
  const metrics = [
    ["Owned", insights.totalOwned], ["Invested", `$${insights.totalCost.toLocaleString()}`], ["Total wears", insights.totalWears],
    ["Most worn", getDemoFragranceById(insights.mostWornId)!.name], ["Highest rated", getDemoFragranceById(insights.highestRatedId)!.name], ["Best cost / wear", getDemoFragranceById(insights.bestCostPerWearId)!.name],
  ];
  return (
    <section className="page">
      <PageHeader eyebrow="Collection intelligence" title="Insights" description="Patterns in what you own, reach for, and might use more intentionally." />
      <div className="metric-grid">{metrics.map(([label, value]) => <Card key={label}><CardContent><span>{label}</span><strong className={typeof value === "number" ? "metric-number" : ""}>{value}</strong></CardContent></Card>)}</div>
      <div className="insight-charts">
        <Card><CardContent><p className="eyebrow">Character</p><h2 className="serif">Accord distribution</h2><div className="chart" role="img" aria-label={`Accord distribution: ${insights.accordDistribution.map((item) => `${item.name} ${item.value}%`).join(", ")}`}><ResponsiveContainer width="100%" height={260}><BarChart data={insights.accordDistribution} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#ded8cc" /><XAxis dataKey="name" tick={{ fontSize: 12 }} /><YAxis tick={{ fontSize: 12 }} /><Tooltip /><Bar dataKey="value" fill="#b7772f" radius={[8,8,0,0]} /></BarChart></ResponsiveContainer></div></CardContent></Card>
        <Card><CardContent><p className="eyebrow">Ingredients</p><h2 className="serif">Note frequency</h2><div className="note-bars">{insights.noteFrequency.map((item) => <div key={item.name}><span>{item.name}</span><Progress value={item.value * 12} label={`${item.name} frequency`} /><strong>{item.value}</strong></div>)}</div><p className="muted">Frequency reflects preference, not an automatic gap.</p></CardContent></Card>
      </div>
      <Card className="coverage-card"><CardContent><p className="eyebrow">Use-case coverage</p><h2 className="serif">Where your wardrobe is ready</h2><div className="coverage-grid">{insights.coverage.map((item) => <div key={item.name}><div><strong>{item.name}</strong><Badge className={`coverage--${item.label.toLowerCase()}`}>{item.label}</Badge></div><Progress value={item.score} label={`${item.name} coverage`} /></div>)}</div></CardContent></Card>
      <div className="grid grid-2 insight-notes"><Card><CardContent><Badge>Underrepresented</Badge><h2 className="serif">Warm-weather formality</h2><p>Your collection covers casual summer days well, but has fewer polished options for warm formal events. This is a use-case opportunity—not a claim that you need more notes.</p></CardContent></Card><Card><CardContent><Badge>Overrepresented</Badge><h2 className="serif">Clean woody overlap</h2><p>Several favorites occupy a similar quiet office role. That is a clear preference; consider rotation before treating it as redundancy.</p></CardContent></Card></div>
    </section>
  );
}
