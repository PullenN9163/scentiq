"use client";

import Link from "next/link";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { RecommendationCard } from "@/features/recommendations/recommendation-card";
import { formatEventTime } from "@/lib/calendar";
import type { CalendarEvent } from "@/types/api";
import type { WearPlan } from "@/types/wear-intelligence";

export function WeekPlanner({plan,events=[]}: {plan:WearPlan;events?:CalendarEvent[]}) {
  const start=new Date(`${plan.local_date}T12:00:00Z`);
  const dates=Array.from({length:7},(_,index)=>{const date=new Date(start);date.setUTCDate(date.getUTCDate()+index);return date.toISOString().slice(0,10);});
  return <section className="page"><PageHeader eyebrow="Your next seven days" title="My Week" description="One ScentIQ engine, with a separate match for materially different plans."/>
    {plan.gaps.map(gap=><p role="status" className="muted" key={gap}>{gap}</p>)}
    {plan.recommendations.length === 0 && <Card><CardContent><p>Add an owned fragrance before planning a week.</p><Button asChild><Link href="/collection">Open collection</Link></Button></CardContent></Card>}
    <nav className="week-day-nav" aria-label="Jump to day">{dates.map(date=><a key={date} href={`#day-${date}`}>{new Date(`${date}T12:00:00Z`).toLocaleDateString("en-US",{weekday:"short",timeZone:"UTC"})}</a>)}</nav>
    <div className="week-plan">{dates.map(date=>{
      const recommendations=plan.recommendations.filter(result=>result.context.local_date===date);
      const dayEvents=events.filter(event=>event.is_all_day ? event.starts_at.slice(0,10)===date : new Intl.DateTimeFormat("en-CA",{timeZone:plan.timezone}).format(new Date(event.starts_at))===date);
      return <section key={date} id={`day-${date}`} data-testid="week-day" className="week-plan-day"><h2 className="serif">{new Date(`${date}T12:00:00Z`).toLocaleDateString("en-US",{weekday:"long",month:"short",day:"numeric",timeZone:"UTC"})}</h2>
        {dayEvents.map(event=><p key={event.id}><strong>{formatEventTime(event,plan.timezone)}</strong> · {event.title}</p>)}
        {recommendations.map(result=><RecommendationCard key={result.context_key} recommendation={result} compact/>)}
      </section>;
    })}</div>
  </section>;
}
