"use client";

import { CloudSun, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PageHeader } from "@/components/shared/page-header";
import { PreviewNotice } from "@/components/shared/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { previewEvents, previewWeather } from "@/lib/preview";
import { rankFragrances, seasonForMonth } from "@/lib/catalog-ranking";
import { toneFor } from "@/lib/tone";
import type { FragranceDetail } from "@/types/api";

export function WeekPlanner({ owned }: { owned: FragranceDetail[] }) {
  const [offsets, setOffsets] = useState<Record<string, number>>({});
  return (
    <section className="page">
      <PageHeader eyebrow="September 22–28" title="My Week" description="Collection choices against preview weather and events." />
      <PreviewNotice>Weather and calendar inputs are previews. Every fragrance shown comes from your owned collection; nothing is saved.</PreviewNotice>
      {owned.length === 0 ? <Card className="empty-panel"><h2>Your collection is empty</h2><p>Add an owned fragrance before planning a week.</p><Button asChild><Link href="/collection">Open collection</Link></Button></Card> : <div className="week-list">{previewWeather.map((day) => { const events = previewEvents.filter((event) => event.date === day.date); const month = Number(day.date.slice(5, 7)) - 1; const daypart = events.some((event) => Number(event.time.slice(0, 2)) >= 17) ? "night" : "day"; const ranked = rankFragrances(owned, { season: seasonForMonth(month), daypart, coolWeather: day.high < 68 }); const index = (offsets[day.date] ?? 0) % ranked.length; const fragrance = ranked[index]; return <Card key={day.date} className="day-card" data-testid="week-day"><div className="day-card__date"><strong>{new Date(`${day.date}T12:00:00Z`).toLocaleDateString("en-US", { weekday: "long", timeZone: "UTC" })}</strong><span><CloudSun size={16} />{day.high}° · {day.condition}</span></div><div className="day-card__events">{events.length ? events.map((event) => <span key={event.time}><strong>{event.time}</strong>{event.title}</span>) : <span className="muted">Open day</span>}</div><div className="day-card__scent" style={{ "--scent-tone": toneFor(fragrance.id) } as React.CSSProperties}><span className="scent-swatch" /><div><Badge>Collection match</Badge><h2 className="serif">{fragrance.name}</h2><p>{fragrance.brand.name} · {fragrance.projection_level ?? "projection unknown"}</p></div></div><div className="day-card__actions"><Button size="sm" variant="secondary" onClick={() => setOffsets((current) => ({ ...current, [day.date]: index + 1 }))}><RefreshCw size={15} />Alternative</Button><Button asChild size="sm" variant="ghost"><Link href={`/collection/${fragrance.id}`}>Details</Link></Button></div></Card>; })}</div>}
    </section>
  );
}
