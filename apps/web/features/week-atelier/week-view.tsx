"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { X } from "lucide-react";
import { useEffect, useRef, useState, useSyncExternalStore, useTransition } from "react";
import { toast } from "sonner";

import { Button } from "@/components/atelier/button";
import { FragranceRow } from "@/components/atelier/fragrance-row";
import { Plate } from "@/components/atelier/plate";
import { plateFragrance } from "@/components/atelier/plate-fragrance";
import { Sheet } from "@/components/atelier/sheet";
import { AtelierEmpty } from "@/components/atelier/states";
import { EventCorrectionForm } from "@/features/dashboard/events-card";
import { RecommendationHero } from "@/features/today/recommendation-hero";
import { recommendationCaption, selectedCandidate } from "@/features/today/today-copy";
import { accordFor } from "@/lib/accord";
import { formatEventTime, occasionLabel, type CalendarResult } from "@/lib/calendar";
import { motionTokens } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { conditionLabel } from "@/lib/weather";
import { decideRecommendation } from "@/lib/server/recommendation-actions";
import type { CalendarEvent, ForecastDay, TemperatureUnit } from "@/types/api";
import type { WearCandidate, WearPlan, WearRecommendation } from "@/types/wear-intelligence";

import { buildWeek, eventSummary, rangeLabel, type WeekDay } from "./week-copy";
import styles from "./week-view.module.css";

const NOTE_KEY = "scentiq-week-calendar-note";
const noSubscription = () => () => {};
function readDismissed(): boolean {
  try { return window.localStorage.getItem(NOTE_KEY) === "dismissed"; } catch { return false; }
}

/** The Atelier Week: seven day cells, the selected day's pick and the day's events. */
export function WeekView({
  plan,
  calendar,
  forecast,
  location,
  timeZone,
  unit,
  emptyCollection = false,
}: {
  plan: WearPlan;
  calendar: CalendarResult;
  forecast: ForecastDay[];
  location: string | null;
  timeZone: string;
  unit: TemperatureUnit | null;
  emptyCollection?: boolean;
}) {
  const events = calendar.status === "ok" ? calendar.events : [];
  const days = buildWeek(plan, events, forecast, timeZone, unit);
  const [selectedDate, setSelectedDate] = useState(days[0]?.date ?? plan.local_date);
  const [editing, setEditing] = useState<CalendarEvent | null>(null);
  const storedDismissal = useSyncExternalStore(noSubscription, readDismissed, () => false);
  const [noteDismissed, setNoteDismissed] = useState(false);
  const cells = useRef<Map<string, HTMLButtonElement>>(new Map());
  const selected = days.find((day) => day.date === selectedDate) ?? days[0];

  useEffect(() => {
    cells.current.get(selectedDate)?.scrollIntoView?.({ inline: "center", block: "nearest", behavior: "smooth" });
  }, [selectedDate]);

  if (emptyCollection) {
    return (
      <div className="at-page">
        <AtelierEmpty headingLevel={1} title="Your shelf starts here" action={<Button asChild variant="outline"><Link href="/collection">Add fragrance</Link></Button>}>Add a bottle, decant or sample and ScentIQ can plan your week around it.</AtelierEmpty>
      </div>
    );
  }

  const caption = [days.length ? rangeLabel(days[0].date, days[days.length - 1].date) : null, location].filter(Boolean).join(" · ");
  const showConnect = calendar.status === "not_connected" && !storedDismissal && !noteDismissed;
  const reconnect = calendar.status === "ok" && calendar.needsReconnect;
  const [first, ...rest] = selected?.recommendations ?? [];

  function dismiss() {
    setNoteDismissed(true);
    try { window.localStorage.setItem(NOTE_KEY, "dismissed"); } catch { /* this visit only */ }
  }

  function moveSelection(index: number) {
    const next = days[Math.max(0, Math.min(days.length - 1, index))];
    if (next) { setSelectedDate(next.date); cells.current.get(next.date)?.focus(); }
  }

  return (
    <div className="at-page">
      <header className={styles.header}>
        <h1 className={styles.title}>Week</h1>
        <p className="at-caption">{caption}</p>
      </header>
      {plan.gaps.length > 0 ? <p className={cn("at-caption", styles.note)}>{plan.gaps.join(" ")}</p> : null}
      {showConnect ? (
        <p className={cn("at-caption", styles.note, styles.dismissible)}>
          <span><Link className="at-link" href="/settings#calendar">Connect a calendar</Link> to plan around your events.</span>
          <button type="button" className={styles.dismiss} aria-label="Dismiss calendar suggestion" onClick={dismiss}><X aria-hidden="true" /></button>
        </p>
      ) : null}
      {reconnect ? <p className={cn("at-caption", styles.note, styles.warning)}>A calendar needs attention. <Link href="/settings#calendar">Reconnect</Link></p> : null}

      <div className={styles.strip} role="listbox" aria-label="Days" aria-orientation="horizontal">
        {days.map((day, index) => (
          <DayCell
            key={day.date}
            day={day}
            selected={day.date === selectedDate}
            onSelect={() => setSelectedDate(day.date)}
            onKeyDown={(event) => {
              if (event.key === "ArrowRight") { event.preventDefault(); moveSelection(index + 1); }
              if (event.key === "ArrowLeft") { event.preventDefault(); moveSelection(index - 1); }
            }}
            refCallback={(element) => { if (element) cells.current.set(day.date, element); else cells.current.delete(day.date); }}
          />
        ))}
      </div>

      <div className={styles.detail}>
        <div className={styles.dayMain}>
          <AnimatePresence mode="wait" initial={false}>
            <motion.div key={selected?.date} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ ...motionTokens.settle, duration: 0.15 }}>
              {first && selected ? (
                <>
                  <RecommendationHero
                    recommendation={first}
                    compact
                    headingLevel={2}
                    mode={selected.isToday ? undefined : "plan"}
                    chips={[
                      { label: new Date(`${selected.date}T12:00:00Z`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" }) },
                      ...(selected.forecast ? [{ label: `${selected.forecastLabel?.split(" ")[0] ?? ""} ${selected.forecast.condition === "unknown" ? "" : conditionLabel(selected.forecast.condition).toLowerCase()}`.trim() }] : []),
                      ...(first.context.occasion && calendar.status !== "not_connected" ? [{ label: occasionLabel(first.context.occasion) }] : []),
                    ]}
                  />
                  {rest.length > 0 ? (
                    <div className={styles.more}>
                      {rest.map((recommendation) => <MoreRow key={recommendation.id} recommendation={recommendation} events={events} timeZone={timeZone} />)}
                    </div>
                  ) : null}
                </>
              ) : (
                <AtelierEmpty title="Nothing planned for this day">ScentIQ has no pick for this day yet. Add more owned fragrances to widen the options.</AtelierEmpty>
              )}
            </motion.div>
          </AnimatePresence>
        </div>
        <aside className={styles.side}>
          {calendar.status === "ok" ? (
            <section aria-labelledby="your-day">
              <h2 id="your-day" className="at-title">Your day</h2>
              {selected && selected.events.length > 0 ? (
                <ul className={styles.events}>
                  {selected.events.map((event) => (
                    <li key={event.id} className={styles.event}>
                      <span className="at-caption at-tabular">{formatEventTime(event, timeZone)}</span>
                      <span className={styles.eventText}><b>{event.title}</b><span className="at-caption">{occasionLabel(event.occasion)}</span></span>
                      <Button size="sm" variant="text" onClick={() => setEditing(event)} aria-label={`Edit ${event.title}`}>Edit</Button>
                    </li>
                  ))}
                </ul>
              ) : <p className="at-caption">Nothing scheduled. An open day.</p>}
            </section>
          ) : calendar.status === "unavailable" ? (
            <p className="at-caption" role="status">Your calendar cannot be loaded right now. Try again shortly.</p>
          ) : null}
          {first && first.alternatives.length > 0 ? (
            <section aria-labelledby="other-options">
              <h2 id="other-options" className="at-title">Other good options</h2>
              <div className={styles.options}>
                {first.alternatives.slice(0, 4).map((candidate) => <OptionRow key={candidate.fragrance.id} recommendation={first} candidate={candidate} />)}
              </div>
            </section>
          ) : null}
        </aside>
      </div>

      <Sheet open={editing !== null} onOpenChange={(open) => { if (!open) setEditing(null); }} title={editing ? `Edit ${editing.title}` : "Edit event"}>
        {editing ? <div className="atelier-legacy-form"><EventCorrectionForm event={editing} /></div> : null}
      </Sheet>
    </div>
  );
}

function DayCell({ day, selected, onSelect, onKeyDown, refCallback }: { day: WeekDay; selected: boolean; onSelect: () => void; onKeyDown: (event: React.KeyboardEvent) => void; refCallback: (element: HTMLButtonElement | null) => void }) {
  const pick = day.recommendations[0] ? selectedCandidate(day.recommendations[0]).fragrance : null;
  const summary = eventSummary(day.events);
  return (
    <button
      ref={refCallback}
      type="button"
      role="option"
      aria-selected={selected}
      tabIndex={selected ? 0 : -1}
      className={cn(styles.day, day.isToday && styles.today, selected && styles.selected)}
      onClick={onSelect}
      onKeyDown={onKeyDown}
      data-testid="day-cell"
    >
      <b>{day.label}{day.isToday ? <span className={styles.todayWord}> · Today</span> : null}</b>
      <span className={styles.dayMeta}>{day.forecastLabel ?? " "}</span>
      {pick ? (
        <Plate fragrance={plateFragrance(pick)} accord={accordFor(pick)} className={styles.dayPlate} compact decorative sizes="160px" />
      ) : (
        <span className={styles.planTile}>Plan</span>
      )}
      <span className={styles.dayName}>{pick?.name ?? summary ?? " "}</span>
      {pick && summary ? <span className={styles.dayMeta}>{summary}</span> : null}
    </button>
  );
}

function MoreRow({ recommendation, events, timeZone }: { recommendation: WearRecommendation; events: CalendarEvent[]; timeZone: string }) {
  const fragrance = selectedCandidate(recommendation).fragrance;
  return <FragranceRow className={styles.moreRow} fragrance={plateFragrance(fragrance)} accord={accordFor(fragrance)} caption={recommendationCaption(recommendation, events, timeZone)} captionFirst href={`/collection/${fragrance.id}`} />;
}

function OptionRow({ recommendation, candidate }: { recommendation: WearRecommendation; candidate: WearCandidate }) {
  const router = useRouter();
  const [used, setUsed] = useState(recommendation.decision?.selected_fragrance_id === candidate.fragrance.id);
  const [pending, startTransition] = useTransition();
  function use() {
    startTransition(async () => {
      const result = await decideRecommendation(recommendation.id, "replaced", candidate.fragrance.id);
      if (!result.ok) { toast.error(result.error); return; }
      setUsed(true);
      toast.success(`Planned ${candidate.fragrance.name}`);
      router.refresh();
    });
  }
  return (
    <FragranceRow
      className={styles.optionRow}
      fragrance={plateFragrance(candidate.fragrance)}
      accord={accordFor(candidate.fragrance)}
      caption={candidate.reasons[0] ?? candidate.fragrance.brand.name}
      href={`/collection/${candidate.fragrance.id}`}
      trailing={<Button size="sm" variant="text" disabled={pending || used} onClick={use}>{used ? "Planned" : pending ? "Saving…" : "Use this"}</Button>}
    />
  );
}

export function WeekSkeleton() {
  return (
    <div className="at-page" aria-busy="true">
      <span className="sr-only" role="status">Loading your week</span>
      <span className="at-skeleton" style={{ width: 160, height: 56, marginBottom: 24 }} />
      <div className={styles.strip}>
        {Array.from({ length: 7 }, (_, index) => <span key={index} className={cn("at-skeleton", styles.skeletonCell)} />)}
      </div>
      <span className="at-skeleton" style={{ display: "block", height: 320, marginTop: 32, borderRadius: 28 }} />
    </div>
  );
}
