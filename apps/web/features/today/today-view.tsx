"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { X } from "lucide-react";
import { motion } from "motion/react";
import { useState, useSyncExternalStore, useTransition, type ReactNode } from "react";
import { toast } from "sonner";

import { Button } from "@/components/atelier/button";
import { FragranceRow } from "@/components/atelier/fragrance-row";
import { plateFragrance } from "@/components/atelier/plate-fragrance";
import { accordFor, accordVars } from "@/lib/accord";
import { localDate, occasionLabel, type CalendarResult } from "@/lib/calendar";
import { motionTokens } from "@/lib/motion";
import { cn } from "@/lib/utils";
import type { WeatherResult } from "@/lib/weather";
import { decideRecommendation } from "@/lib/server/recommendation-actions";
import type { CollectionInsights, Me, WearLogEntry } from "@/types/api";
import type { WearCandidate, WearPlan, WearRecommendation } from "@/types/wear-intelligence";

import { HeroSkeleton, RecommendationHero, type ContextChip } from "./recommendation-hero";
import { formatLongDate, latelyLine, recommendationCaption, selectedCandidate, weatherChip } from "./today-copy";
import styles from "./today-view.module.css";

const CALENDAR_NOTE_KEY = "scentiq-today-calendar-note";

function readDismissed(): boolean {
  try { return window.localStorage.getItem(CALENDAR_NOTE_KEY) === "dismissed"; } catch { return false; }
}
const noSubscription = () => () => {};

/** The Atelier Today page: one hero pick, later today, the week ahead, a blend idea. */
export function TodayView({
  plan,
  planFailed = false,
  me,
  insights,
  recentWears,
  weather,
  calendar,
  timeZone,
  week,
}: {
  plan?: WearPlan;
  /** The pick could not be loaded; the rest of the page still renders. */
  planFailed?: boolean;
  me: Me;
  insights: CollectionInsights;
  recentWears: WearLogEntry[];
  weather: WeatherResult;
  /** Already narrowed to today in `timeZone`. */
  calendar: CalendarResult;
  timeZone: string;
  /** The "This week" section, streamed separately so it never delays the hero. */
  week?: ReactNode;
}) {
  const router = useRouter();
  const recommendations = (plan?.recommendations ?? []) as WearRecommendation[];
  const [first, ...later] = recommendations;
  const [pick, setPick] = useState<WearCandidate | null>(first ? selectedCandidate(first) : null);
  const storedDismissal = useSyncExternalStore(noSubscription, readDismissed, () => false);
  const [noteDismissed, setNoteDismissed] = useState(false);
  const today = plan?.local_date ?? localDate(new Date(), timeZone);
  const location = me.preferences.location_label ?? me.preferences.location;
  const caption = [formatLongDate(today), location].filter(Boolean).join(" · ");

  if (insights.total_items === 0) {
    return (
      <div className="at-page">
        <section className={styles.empty}>
          <h1 className="at-title">Your shelf starts here</h1>
          <p className="at-body">Add a bottle, decant or sample and ScentIQ can start planning around it.</p>
          <Button asChild variant="outline"><Link href="/collection">Add fragrance</Link></Button>
        </section>
      </div>
    );
  }

  const chips: ContextChip[] = [];
  const weatherLabel = weatherChip(weather, today);
  if (weatherLabel) chips.push({ label: weatherLabel });
  else if (weather.status === "location_required" || weather.status === "location_unresolved") chips.push({ label: "Add your location", href: "/settings" });
  if (first?.context.occasion && calendar.status !== "not_connected") chips.push({ label: occasionLabel(first.context.occasion) });

  const events = calendar.status === "ok" ? calendar.events : [];
  const showCalendarNote = calendar.status === "not_connected" && !storedDismissal && !noteDismissed;
  const reconnect = calendar.status === "ok" && calendar.needsReconnect;
  const partner = later[0] ? selectedCandidate(later[0]).fragrance : null;
  const lately = latelyLine(recentWears, timeZone);

  function dismissNote() {
    setNoteDismissed(true);
    try { window.localStorage.setItem(CALENDAR_NOTE_KEY, "dismissed"); } catch { /* private mode: dismiss for this visit only */ }
  }

  return (
    <div className="at-page">
      <p className={cn("at-caption", styles.dateline)}>{caption}</p>
      <div className={styles.layout}>
        <div className={styles.main}>
          <div className={styles.heroSlot}>
          {first && pick ? (
            <RecommendationHero recommendation={first} chips={chips} onPickChange={setPick} bloom />
          ) : planFailed ? (
            <section className={styles.empty}>
              <h1 className="at-title">We could not load today&apos;s pick.</h1>
              <p className="at-caption">Your weather and calendar are still here. This is usually a short delay.</p>
              <Button variant="outline" onClick={() => router.refresh()}>Try again</Button>
            </section>
          ) : (
            <section className={styles.empty}>
              <h1 className="at-title">Add an owned fragrance to receive recommendations.</h1>
              <Button asChild variant="outline"><Link href="/collection">Open collection</Link></Button>
            </section>
          )}
          {plan && plan.gaps.length > 0 ? <p className={cn("at-caption", styles.note)}>{plan.gaps.join(" ")}</p> : null}
          {showCalendarNote ? (
            <p className={cn("at-caption", styles.note, styles.dismissible)}>
              <span><Link className="at-link" href="/settings#calendar">Connect a calendar</Link> to plan around your day.</span>
              <button type="button" className={styles.dismiss} onClick={dismissNote} aria-label="Dismiss calendar suggestion"><X aria-hidden="true" /></button>
            </p>
          ) : null}
          {reconnect ? (
            <p className={cn("at-caption", styles.note, styles.warning)}>
              Your calendar needs attention. <Link href="/settings#calendar">Reconnect</Link>
            </p>
          ) : null}
          </div>
          {lately ? (
            <p className={styles.lately}><b>Lately</b> <span>{lately}</span></p>
          ) : null}
        </div>
        <div className={styles.side}>
          {later.length > 0 ? (
            <section className={styles.later} aria-labelledby="later-today">
              <h2 id="later-today" className="at-title">Later today</h2>
              <div className={styles.laterList}>
                {later.map((recommendation, index) => (
                  <motion.div key={recommendation.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ ...motionTokens.quick, delay: Math.min(index, 8) * 0.03 }}>
                    <LaterRow recommendation={recommendation} events={events} timeZone={timeZone} />
                  </motion.div>
                ))}
              </div>
            </section>
          ) : null}
          {week ? <div className={styles.week}>{week}</div> : null}
          {pick ? (
            <Link className={styles.blend} href={`/layering?a=${pick.fragrance.id}`}>
              <span className={styles.blendMark} aria-hidden="true">
                <i style={accordVars(accordFor(pick.fragrance))} />
                <i style={accordVars(partner ? accordFor(partner) : accordFor(pick.fragrance))} />
              </span>
              <span className={styles.blendText}>
                <b>{partner ? `Blend ${pick.fragrance.name} with ${partner.name}` : `Start a blend with ${pick.fragrance.name}`}</b>
                {partner && later[0] ? <span className="at-caption">{later[0].context.daypart === "night" ? "For tonight" : "For later today"}</span> : null}
              </span>
              <span className={cn("at-caption", styles.blendGo)} aria-hidden="true">Open →</span>
            </Link>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function LaterRow({ recommendation, events, timeZone }: { recommendation: WearRecommendation; events: Parameters<typeof recommendationCaption>[1]; timeZone: string }) {
  const candidate = selectedCandidate(recommendation);
  const fragrance = candidate.fragrance;
  const [planned, setPlanned] = useState(recommendation.decision?.action === "accepted" || recommendation.decision?.action === "replaced");
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  function plan() {
    startTransition(async () => {
      const result = await decideRecommendation(recommendation.id, "accepted", fragrance.id);
      if (!result.ok) { setError(result.error); toast.error(result.error); return; }
      setError(null);
      setPlanned(true);
      toast.success("Planned");
    });
  }
  return (
    <div className={styles.laterRow}>
      <FragranceRow
        fragrance={plateFragrance(fragrance)}
        accord={accordFor(fragrance)}
        caption={recommendationCaption(recommendation, events, timeZone)}
        captionFirst
        href={`/collection/${fragrance.id}`}
        trailing={<Button size="sm" variant="text" disabled={pending || planned} onClick={plan}>{planned ? "Planned" : pending ? "Planning…" : "Plan it"}</Button>}
      />
      {error ? <p className="at-error" role="alert">{error}</p> : null}
    </div>
  );
}

/** Route-level loading shape: a hero and three rows. */
export function TodaySkeleton() {
  return (
    <div className="at-page" aria-busy="true">
      <span className="sr-only" role="status">Loading your day</span>
      <span className={cn("at-skeleton", styles.skeletonLine)} />
      <div className={styles.layout}>
        <div className={styles.main}><div className={styles.heroSlot}><HeroSkeleton /></div></div>
        <div className={styles.side}>
          {[0, 1, 2].map((index) => (
            <div key={index} className={styles.skeletonRow} aria-hidden="true">
              <span className="at-skeleton" style={{ width: 52, height: 60 }} />
              <span style={{ display: "grid", gap: 8 }}>
                <span className="at-skeleton" style={{ width: 160, height: 16 }} />
                <span className="at-skeleton" style={{ width: 100, height: 12 }} />
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
