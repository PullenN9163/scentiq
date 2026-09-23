"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { CalendarPlus, Check, CloudSun, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { events, getDemoFragranceById, getDemoWeek, weather } from "@/lib/demo";
import type { RecommendationCandidate } from "@/types/demo";

const schema = z.object({
  title: z.string().trim().min(1, "Title is required"), date: z.string().min(1, "Date is required"),
  time: z.string().min(1, "Time is required"), type: z.string(), setting: z.string(), formality: z.string(),
});
type FormValues = z.infer<typeof schema>;

export function WeekPlanner() {
  const week = getDemoWeek();
  const [selections, setSelections] = useState<Record<string, RecommendationCandidate>>({});
  const [accepted, setAccepted] = useState<string[]>([]);
  const [replaceDate, setReplaceDate] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [addedEvent, setAddedEvent] = useState<FormValues | null>(null);
  const { register, handleSubmit, formState: { errors }, reset } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { title: "", date: "", time: "", type: "Casual", setting: "Indoor", formality: "Relaxed" } });

  const addEvent = (values: FormValues) => { setAddedEvent(values); setFormOpen(false); reset(); };
  return (
    <section className="page">
      <PageHeader eyebrow="September 22–28" title="My Week" description="A clear plan for every forecast and occasion." action={<Button onClick={() => setFormOpen(true)}><CalendarPlus size={17} />Add manual event</Button>} />
      {addedEvent && <p className="success-note" role="status">Added “{addedEvent.title}” to this demo session.</p>}
      <div className="week-list">
        {week.map((day, index) => {
          const chosen = selections[day.date] ?? day.primary;
          const fragrance = getDemoFragranceById(chosen.fragranceId)!;
          const dayWeather = weather[index];
          const dayEvents = [...events.filter((event) => event.date === day.date), ...(addedEvent?.date === day.date ? [{ ...addedEvent, id: "manual-event" }] : [])];
          return (
            <Card key={day.date} className="day-card" data-testid="week-day">
              <div className="day-card__date"><strong>{new Date(`${day.date}T12:00:00`).toLocaleDateString("en-US", { weekday: "long" })}</strong><span>{new Date(`${day.date}T12:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</span><span><CloudSun size={16} />{dayWeather.high}° · {dayWeather.condition}</span></div>
              <div className="day-card__events">{dayEvents.length ? dayEvents.map((event) => <span key={event.id}><strong>{event.time}</strong>{event.title}<small>{event.setting} · {event.formality}</small></span>) : <span className="muted">Open day</span>}</div>
              <div className="day-card__scent" style={{ "--scent-tone": fragrance.tone } as React.CSSProperties}><span className="scent-swatch" /><div><Badge>{accepted.includes(day.date) ? "Accepted" : day.status}</Badge><h2 className="serif">{fragrance.name}</h2><p>{fragrance.brand} · {chosen.sprays} sprays</p><small>{chosen.reason}</small></div></div>
              <div className="day-card__actions"><Button size="sm" onClick={() => setAccepted((dates) => [...new Set([...dates, day.date])])}><Check size={15} />Accept</Button><Button size="sm" variant="secondary" onClick={() => setReplaceDate(day.date)}><RefreshCw size={15} />Replace recommendation</Button><Button size="sm" variant="ghost" onClick={() => { const next = day.alternatives.find((candidate) => candidate.fragranceId !== chosen.fragranceId) ?? day.primary; setSelections((current) => ({ ...current, [day.date]: next })); setAccepted((dates) => dates.filter((date) => date !== day.date)); }}>Generate alternative</Button><Button asChild size="sm" variant="ghost"><Link href={`/collection/${fragrance.id}`}>Details</Link></Button></div>
            </Card>
          );
        })}
      </div>
      <Dialog open={Boolean(replaceDate)} onOpenChange={(open) => { if (!open) setReplaceDate(null); }}><DialogContent title="Choose another direction" eyebrow="Ranked alternatives">{replaceDate && week.find((day) => day.date === replaceDate)!.alternatives.map((candidate) => { const option = getDemoFragranceById(candidate.fragranceId)!; return <button className="option-row" key={candidate.fragranceId} onClick={() => { setSelections((current) => ({ ...current, [replaceDate]: candidate })); setAccepted((dates) => dates.filter((date) => date !== replaceDate)); setReplaceDate(null); }} aria-label={`Choose ${option.name}`}><span className="scent-swatch" style={{ "--scent-tone": option.tone } as React.CSSProperties} /><span><strong>{option.name}</strong><small>{option.brand} · {candidate.reason}</small></span><Badge>{candidate.score}%</Badge></button>; })}</DialogContent></Dialog>
      <Dialog open={formOpen} onOpenChange={setFormOpen}><DialogContent title="Add to your week" eyebrow="Demo event"><form className="form-grid" onSubmit={handleSubmit(addEvent)} noValidate><div className="field field--full"><Label htmlFor="event-title">Title</Label><Input id="event-title" aria-invalid={Boolean(errors.title)} aria-describedby={errors.title ? "event-title-error" : undefined} {...register("title")} />{errors.title && <p id="event-title-error" className="field-error">{errors.title.message}</p>}</div><div className="field"><Label htmlFor="event-date">Date</Label><Input id="event-date" type="date" aria-invalid={Boolean(errors.date)} aria-describedby={errors.date ? "event-date-error" : undefined} {...register("date")} />{errors.date && <p id="event-date-error" className="field-error">{errors.date.message}</p>}</div><div className="field"><Label htmlFor="event-time">Start time</Label><Input id="event-time" type="time" aria-invalid={Boolean(errors.time)} aria-describedby={errors.time ? "event-time-error" : undefined} {...register("time")} />{errors.time && <p id="event-time-error" className="field-error">{errors.time.message}</p>}</div>{[["type", "Event type", ["Office", "Casual", "Date", "Formal", "Gym", "Travel", "Nightlife"]], ["setting", "Setting", ["Indoor", "Outdoor", "Mixed"]], ["formality", "Formality", ["Relaxed", "Smart", "Formal"]]].map(([name, label, options]) => <div className="field" key={name as string}><Label htmlFor={`event-${name}`}>{label as string}</Label><select className="select" id={`event-${name}`} {...register(name as "type" | "setting" | "formality")}>{(options as string[]).map((option) => <option key={option}>{option}</option>)}</select></div>)}<div className="field--full cluster"><Button type="submit">Add to week</Button><Button type="button" variant="ghost" onClick={() => setFormOpen(false)}>Cancel</Button></div></form></DialogContent></Dialog>
    </section>
  );
}
