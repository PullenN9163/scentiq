"use client";

import { CalendarDays, Check, CloudSun, Layers3, RefreshCw, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { getDemoFragranceById, getDemoToday, getDemoWeek } from "@/lib/demo";

export function TodayDashboard() {
  const today = getDemoToday();
  const candidates = [today.recommendation.primary, ...today.recommendation.alternatives];
  const [candidateIndex, setCandidateIndex] = useState(0);
  const [dismissed, setDismissed] = useState(false);
  const [worn, setWorn] = useState(false);
  const selected = candidates[candidateIndex];
  const fragrance = getDemoFragranceById(selected.fragranceId)!;

  return (
    <section className="page">
      <PageHeader eyebrow="Tuesday · September 22" title="Today" description={`${today.user.location} · ${today.weather.condition} · ${today.weather.high}° / ${today.weather.low}°`} />
      {dismissed ? (
        <Card><CardContent className="empty-panel"><h2 className="serif">Recommendation dismissed</h2><p className="muted">No changes were saved. Bring it back whenever you are ready.</p><Button onClick={() => setDismissed(false)}>Restore recommendation</Button></CardContent></Card>
      ) : (
        <div className="today-layout">
          <Card className="recommendation-card">
            <div className="recommendation-art" style={{ "--bottle-tone": fragrance.tone } as React.CSSProperties}><span>{fragrance.brand}</span><strong>{fragrance.name}</strong></div>
            <CardContent className="recommendation-copy">
              <div className="cluster"><Badge>Top recommendation</Badge><Badge>{selected.score}% match</Badge></div>
              <h2 className="serif">{fragrance.name}</h2><p className="muted">{fragrance.brand} · {fragrance.concentration}</p>
              <Progress value={selected.score} label={`${fragrance.name} match score`} />
              <p className="recommendation-reason">{selected.reason}</p>
              <ul className="reason-list">{today.recommendation.reasons.map((reason) => <li key={reason}><Check size={15} />{reason}</li>)}</ul>
              {today.recommendation.warning && <p className="warning">{today.recommendation.warning}</p>}
              <p><strong>{selected.sprays} sprays</strong> recommended</p>
              <div className="cluster">
                <Button onClick={() => setWorn(true)}><Check size={17} />{worn ? "Marked worn" : "Wear this"}</Button>
                <Button variant="secondary" onClick={() => setCandidateIndex((index) => (index + 1) % candidates.length)}><RefreshCw size={17} />Another option</Button>
                <Button asChild variant="ghost"><Link href={`/collection/${fragrance.id}`}>View details</Link></Button>
                <Button asChild variant="ghost"><Link href={`/layering?a=${fragrance.id}`}><Layers3 size={17} />Layer it</Link></Button>
                <Button variant="ghost" onClick={() => setDismissed(true)}><X size={17} />Dismiss</Button>
              </div>
            </CardContent>
          </Card>
          <aside className="today-rail">
            <Card><CardContent><div className="section-title"><CalendarDays size={19} /><h3>Next up</h3></div>{today.events.map((event) => <div className="event-row" key={event.id}><strong>{event.time}</strong><span>{event.title}<small>{event.setting} · {event.formality}</small></span></div>)}</CardContent></Card>
            <Card><CardContent><div className="section-title"><CloudSun size={19} /><h3>Week ahead</h3></div>{getDemoWeek().slice(1, 4).map((day) => { const item = getDemoFragranceById(day.primary.fragranceId)!; return <div className="week-peek" key={day.date}><span>{new Date(`${day.date}T12:00:00`).toLocaleDateString("en-US", { weekday: "short" })}</span><strong>{item.name}</strong><span>{day.primary.score}%</span></div>; })}</CardContent></Card>
          </aside>
        </div>
      )}
    </section>
  );
}
