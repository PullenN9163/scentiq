"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { CalendarPlus, Check, CloudSun, RefreshCw, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { events, getDemoFragranceById, getDemoWeek, weather } from "@/lib/demo";

const schema = z.object({
  title: z.string().trim().min(1, "Title is required"), date: z.string().min(1, "Date is required"),
  time: z.string().min(1, "Time is required"), type: z.string(), setting: z.string(), formality: z.string(),
});
type FormValues = z.infer<typeof schema>;

export function WeekPlanner() {
  const week = getDemoWeek();
  const [selections, setSelections] = useState<Record<string, string>>({});
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
          const chosenId = selections[day.date] ?? day.primary.fragranceId;
          const fragrance = getDemoFragranceById(chosenId)!;
          const dayWeather = weather[index];
          const dayEvents = events.filter((event) => event.date === day.date);
          return (
            <Card key={day.date} className="day-card" data-testid="week-day">
              <div className="day-card__date"><strong>{new Date(`${day.date}T12:00:00`).toLocaleDateString("en-US", { weekday: "long" })}</strong><span>{new Date(`${day.date}T12:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</span><span><CloudSun size={16} />{dayWeather.high}° · {dayWeather.condition}</span></div>
              <div className="day-card__events">{dayEvents.length ? dayEvents.map((event) => <span key={event.id}><strong>{event.time}</strong>{event.title}<small>{event.setting} · {event.formality}</small></span>) : <span className="muted">Open day</span>}</div>
              <div className="day-card__scent" style={{ "--scent-tone": fragrance.tone } as React.CSSProperties}><span className="scent-swatch" /><div><Badge>{accepted.includes(day.date) ? "Accepted" : day.status}</Badge><h2 className="serif">{fragrance.name}</h2><p>{fragrance.brand} · {day.primary.sprays} sprays</p><small>{day.primary.reason}</small></div></div>
              <div className="day-card__actions"><Button size="sm" onClick={() => setAccepted((dates) => [...new Set([...dates, day.date])])}><Check size={15} />Accept</Button><Button size="sm" variant="secondary" onClick={() => setReplaceDate(day.date)}><RefreshCw size={15} />Replace recommendation</Button><Button asChild size="sm" variant="ghost"><Link href={`/collection/${fragrance.id}`}>Details</Link></Button></div>
            </Card>
          );
        })}
      </div>
      {replaceDate && <div className="modal-backdrop"><div className="modal" role="dialog" aria-modal="true" aria-label="Replace recommendation"><div className="modal__header"><div><p className="eyebrow">Ranked alternatives</p><h2 className="serif">Choose another direction</h2></div><button aria-label="Close replacement" onClick={() => setReplaceDate(null)}><X /></button></div>{week.find((day) => day.date === replaceDate)!.alternatives.map((candidate) => { const option = getDemoFragranceById(candidate.fragranceId)!; return <button className="option-row" key={candidate.fragranceId} onClick={() => { setSelections((current) => ({ ...current, [replaceDate]: candidate.fragranceId })); setReplaceDate(null); }} aria-label={`Choose ${option.name}`}><span className="scent-swatch" style={{ "--scent-tone": option.tone } as React.CSSProperties} /><span><strong>{option.name}</strong><small>{option.brand} · {candidate.reason}</small></span><Badge>{candidate.score}%</Badge></button>; })}</div></div>}
      {formOpen && <div className="modal-backdrop"><div className="modal" role="dialog" aria-modal="true" aria-label="Add manual event"><div className="modal__header"><div><p className="eyebrow">Demo event</p><h2 className="serif">Add to your week</h2></div><button aria-label="Close event form" onClick={() => setFormOpen(false)}><X /></button></div><form className="form-grid" onSubmit={handleSubmit(addEvent)} noValidate><div className="field field--full"><Label htmlFor="event-title">Title</Label><Input id="event-title" {...register("title")} />{errors.title && <p className="field-error">{errors.title.message}</p>}</div><div className="field"><Label htmlFor="event-date">Date</Label><Input id="event-date" type="date" {...register("date")} />{errors.date && <p className="field-error">{errors.date.message}</p>}</div><div className="field"><Label htmlFor="event-time">Start time</Label><Input id="event-time" type="time" {...register("time")} /></div>{[["type", "Event type", ["Office", "Casual", "Date", "Formal", "Gym", "Travel", "Nightlife"]], ["setting", "Setting", ["Indoor", "Outdoor", "Mixed"]], ["formality", "Formality", ["Relaxed", "Smart", "Formal"]]].map(([name, label, options]) => <div className="field" key={name as string}><Label htmlFor={`event-${name}`}>{label as string}</Label><select className="select" id={`event-${name}`} {...register(name as "type" | "setting" | "formality")}>{(options as string[]).map((option) => <option key={option}>{option}</option>)}</select></div>)}<div className="field--full cluster"><Button type="submit">Add to week</Button><Button type="button" variant="ghost" onClick={() => setFormOpen(false)}>Cancel</Button></div></form></div></div>}
    </section>
  );
}
