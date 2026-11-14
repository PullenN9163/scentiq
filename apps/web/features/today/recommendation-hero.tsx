"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useId, useRef, useState, useTransition, type CSSProperties } from "react";
import { toast } from "sonner";

import { Button } from "@/components/atelier/button";
import { Chip } from "@/components/atelier/chip";
import { Field, Select, Stepper, TextInput } from "@/components/atelier/field";
import { centerOf, effectsReduced, playMist, resolveColor } from "@/components/atelier/mist";
import { Plate, plateFragrance } from "@/components/atelier/plate";
import { Sheet } from "@/components/atelier/sheet";
import { WearFeedbackDialog } from "@/features/collection/wear-feedback-dialog";
import { evidenceLabel } from "@/features/recommendations/recommendation-card";
import { accordFor, accordVars } from "@/lib/accord";
import { motionTokens } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { decideRecommendation, nextRecommendation, recommendationFeedback, wearRecommendation } from "@/lib/server/recommendation-actions";
import type { Occasion } from "@/types/api";
import type { WearCandidate, WearRecommendation } from "@/types/wear-intelligence";

import { claimDailyBloom, localDayKey } from "./bloom";
import { accordWords, componentLabel, selectedCandidate, splitReasons } from "./today-copy";
import styles from "./recommendation-hero.module.css";

const OCCASIONS: Occasion[] = ["work", "casual", "date", "dinner", "party", "formal", "gym", "travel", "other"];
const OCCASION_NAMES: Record<Occasion, string> = { work: "Work", casual: "Casual", date: "Date", dinner: "Dinner", party: "Party", formal: "Formal", gym: "Gym", travel: "Travel", other: "Other" };
/** With no answer to "Too strong?", the dislike is recorded after this long. */
const FOLLOW_UP_MS = 10_000;

type BloomOrigin = { x: number; y: number; radius: number; id: number };
let bloomSeq = 0;

/** Where the bloom starts (the bottle) and how far it must reach to cover the hero. */
function bloomFrom(hero: HTMLElement, origin: HTMLElement | null): BloomOrigin {
  const box = hero.getBoundingClientRect();
  const from = (origin ?? hero).getBoundingClientRect();
  const x = from.left - box.left + from.width / 2;
  const y = from.top - box.top + from.height / 2;
  const radius = Math.hypot(Math.max(x, box.width - x), Math.max(y, box.height - y));
  bloomSeq += 1;
  return { x, y, radius, id: bloomSeq };
}

export type ContextChip = { label: string; href?: string };

/**
 * The Today pick: one fragrance on its accord color, the reason, and three
 * responses (Wear it, Not today, Not for me). Action handling is ported from
 * RecommendationCard: the same server actions, retry keys and exhausted state.
 */
export function RecommendationHero({
  recommendation: initialRecommendation,
  chips = [],
  onPickChange,
  mode = "wear",
  wornAt,
  headingLevel = 1,
  compact = false,
  bloom = false,
}: {
  recommendation: WearRecommendation;
  /** Weather and occasion chips, in order; the personal fact chip is added here. */
  chips?: ContextChip[];
  onPickChange?: (candidate: WearCandidate) => void;
  /** "plan" swaps Wear it for Plan it, which accepts the pick without logging a wear. */
  mode?: "wear" | "plan";
  /** Logs the wear on another day (the Week planner). */
  wornAt?: string;
  headingLevel?: 1 | 2;
  /** Smaller name and plate, for the Week planner. */
  compact?: boolean;
  /** Blooms the hero color when a pick first shows (Today). */
  bloom?: boolean;
}) {
  const router = useRouter();
  const [feedbackWear, setFeedbackWear] = useState<string | null>(null);
  return (
    <>
      {feedbackWear && <WearFeedbackDialog wearId={feedbackWear} onClose={() => { setFeedbackWear(null); router.refresh(); }} />}
      <HeroContent
        key={initialRecommendation.id}
        recommendation={initialRecommendation}
        chips={chips}
        onPickChange={onPickChange}
        onWearLogged={setFeedbackWear}
        mode={mode}
        wornAt={wornAt}
        headingLevel={headingLevel}
        compact={compact}
        bloom={bloom}
      />
    </>
  );
}

function HeroContent({
  recommendation: initialRecommendation,
  chips,
  onPickChange,
  onWearLogged,
  mode,
  wornAt,
  headingLevel,
  compact,
  bloom,
}: {
  recommendation: WearRecommendation;
  chips: ContextChip[];
  onPickChange?: (candidate: WearCandidate) => void;
  onWearLogged: (id: string) => void;
  mode: "wear" | "plan";
  wornAt?: string;
  headingLevel: 1 | 2;
  compact: boolean;
  bloom: boolean;
}) {
  const router = useRouter();
  const formId = useId();
  const [recommendation, setRecommendation] = useState(initialRecommendation);
  const retryKey = useRef<{ key: string; reset: boolean } | null>(null);
  const [selected, setSelected] = useState<WearCandidate>(() => selectedCandidate(initialRecommendation));
  const [whyOpen, setWhyOpen] = useState(false);
  const [wearOpen, setWearOpen] = useState(false);
  const [followUp, setFollowUp] = useState(false);
  const [sprays, setSprays] = useState(selected.recommended_sprays);
  const [occasion, setOccasion] = useState<Occasion | "">(initialRecommendation.context.occasion ?? "");
  const [setting, setSetting] = useState(initialRecommendation.context.setting ?? "");
  const [note, setNote] = useState("");
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const hero = useRef<HTMLElement>(null);
  const wearButton = useRef<HTMLButtonElement>(null);
  const plate = useRef<HTMLDivElement>(null);
  const followUpTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [bloomOrigin, setBloomOrigin] = useState<BloomOrigin | null>(null);

  const fragrance = selected.fragrance;
  const accord = accordFor(fragrance);
  const { fact, sentence } = splitReasons(selected.reasons);
  const words = accordWords(fragrance.top_accords ?? []);
  const exhausted = Boolean(recommendation.options_exhausted);
  const Heading = headingLevel === 1 ? "h1" : "h2";

  useEffect(() => () => { if (followUpTimer.current) clearTimeout(followUpTimer.current); }, []);

  // The first pick of the day blooms once on load; later picks bloom in show().
  useEffect(() => {
    if (!bloom || effectsReduced() || !hero.current) return;
    if (!claimDailyBloom(localDayKey())) return;
    setBloomOrigin(bloomFrom(hero.current, plate.current));
  }, [bloom]);

  function show(next: WearRecommendation) {
    const candidate = selectedCandidate(next);
    setRecommendation(next);
    setSelected(candidate);
    setSprays(candidate.recommended_sprays);
    setOccasion(next.context.occasion ?? "");
    setSetting(next.context.setting ?? "");
    onPickChange?.(candidate);
    if (bloom && hero.current && !effectsReduced()) setBloomOrigin(bloomFrom(hero.current, plate.current));
  }

  /** Ask for the next option. Must run inside a transition. */
  async function advance(reset = false) {
    if (!retryKey.current || retryKey.current.reset !== reset) retryKey.current = { key: crypto.randomUUID(), reset };
    const key = retryKey.current.key;
    const result = await nextRecommendation(recommendation.id, key, reset, fragrance.id);
    if (!result.ok) { setError(result.error); toast.error(result.error); return; }
    retryKey.current = null;
    setError(null);
    show(result.data);
  }

  function respond(reason: "not_today" | "too_strong" | "dislike_scent") {
    if (followUpTimer.current) clearTimeout(followUpTimer.current);
    followUpTimer.current = null;
    setFollowUp(false);
    startTransition(async () => {
      const result = await recommendationFeedback(recommendation.id, fragrance.id, reason);
      if (!result.ok) { setError(result.error); toast.error(result.error); return; }
      setError(null);
      if (!exhausted) await advance();
    });
  }

  function notForMe() {
    setFollowUp(true);
    if (followUpTimer.current) clearTimeout(followUpTimer.current);
    followUpTimer.current = setTimeout(() => respond("dislike_scent"), FOLLOW_UP_MS);
  }

  function startOver() {
    startTransition(async () => { await advance(true); });
  }

  function logWear() {
    startTransition(async () => {
      const result = await wearRecommendation(recommendation.id, {
        selected_fragrance_id: fragrance.id,
        sprays,
        notes: note || null,
        occasion: occasion || null,
        setting: setting || null,
        ...(wornAt ? { worn_at: wornAt } : {}),
      });
      if (!result.ok) { setError(result.error); toast.error(result.error); return; }
      setError(null);
      setWearOpen(false);
      onWearLogged(result.data.id);
      toast.success("Wear logged");
      router.refresh();
      if (wearButton.current && plate.current && hero.current) {
        void playMist({ from: centerOf(wearButton.current), to: centerOf(plate.current), color: resolveColor(hero.current, "--ac") });
      }
    });
  }

  function plan() {
    startTransition(async () => {
      const result = await decideRecommendation(recommendation.id, fragrance.id === (recommendation.canonical_fragrance_id ?? initialRecommendation.fragrance.id) ? "accepted" : "replaced", fragrance.id);
      if (!result.ok) { setError(result.error); toast.error(result.error); return; }
      setError(null);
      toast.success("Planned");
    });
  }

  const sprayValid = Number.isInteger(sprays) && sprays >= 1 && sprays <= 30;
  const allChips: ContextChip[] = [...chips, ...(fact ? [{ label: fact }] : [])];

  return (
    <section ref={hero} className={cn(styles.hero, compact && styles.compact)} style={accordVars(accord)} aria-labelledby={`${formId}-name`} data-testid="recommendation-hero" data-accord={accord} data-blooming={bloomOrigin ? "true" : undefined}>
      {bloomOrigin ? (
        <div
          key={bloomOrigin.id}
          className={styles.bloom}
          aria-hidden="true"
          style={{ "--bx": `${bloomOrigin.x}px`, "--by": `${bloomOrigin.y}px`, "--br": `${bloomOrigin.radius}px` } as CSSProperties}
          onAnimationEnd={() => setBloomOrigin(null)}
        />
      ) : null}
      {allChips.length > 0 ? (
        <div className={styles.chips}>
          {allChips.map((chip) => chip.href ? (
            <Link key={chip.label} href={chip.href} className={styles.chipLink}><Chip>{chip.label}</Chip></Link>
          ) : (
            <Chip key={chip.label}>{chip.label}</Chip>
          ))}
        </div>
      ) : null}
      <div className={styles.copy}>
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={fragrance.id}
            className={styles.identity}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ ...motionTokens.settle, duration: 0.15 }}
          >
            <p className={cn("at-overline", styles.house)}>{fragrance.brand.name}</p>
            <Heading id={`${formId}-name`} className={cn("at-display-xl", styles.name)}>
              <Link href={`/collection/${fragrance.id}`} className={styles.nameLink}>{fragrance.name}</Link>
            </Heading>
            {sentence ? <p className={cn("at-body-lg", styles.reason)}>{sentence}</p> : null}
            <p className={styles.meta}>
              {words.length > 0 ? (
                <span>
                  {words.map((word, index) => (
                    <span key={word}>{index > 0 ? " · " : ""}{index === 0 ? <b>{word}</b> : word}</span>
                  ))}
                </span>
              ) : null}
              <span><b>{selected.recommended_sprays}</b> {selected.recommended_sprays === 1 ? "spray" : "sprays"}</span>
            </p>
          </motion.div>
        </AnimatePresence>
        <div className={styles.responses}>
          <Button ref={wearButton} disabled={pending} onClick={() => (mode === "plan" ? plan() : setWearOpen(true))}>{mode === "plan" ? "Plan it" : "Wear it"}</Button>
          <Button variant="soft" disabled={pending} onClick={() => respond("not_today")}>Not today</Button>
          <Button variant="text" disabled={pending} onClick={notForMe} aria-expanded={followUp}>Not for me</Button>
        </div>
        {followUp ? (
          <div className={styles.followUp} role="group" aria-label="Too strong?">
            <span>Too strong?</span>
            <Button size="sm" variant="soft" disabled={pending} onClick={() => respond("too_strong")}>Yes</Button>
            <Button size="sm" variant="text" disabled={pending} onClick={() => respond("dislike_scent")}>Skip</Button>
          </div>
        ) : null}
        {exhausted ? (
          <p className={styles.exhausted} role="status">
            That is everything for today.
            <Button size="sm" variant="text" disabled={pending} onClick={startOver}>Start over</Button>
          </p>
        ) : null}
        {pending ? <p className="sr-only" role="status">Updating your pick…</p> : null}
        {error ? <p className={styles.error} role="alert">{error}</p> : null}
      </div>
      <div className={styles.plateArea}>
        <AnimatePresence mode="wait" initial={false}>
          <motion.div key={fragrance.id} className={styles.plateMotion} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ ...motionTokens.settle, duration: 0.15 }}>
            <Link href={`/collection/${fragrance.id}`} className={styles.plateLink} aria-label={`Open ${fragrance.name}`}>
              <div ref={plate} className={styles.plateBox}>
                <Plate fragrance={plateFragrance(fragrance)} accord={accord} className={styles.plate} priority sizes="(max-width: 700px) 90vw, 280px" />
              </div>
            </Link>
          </motion.div>
        </AnimatePresence>
        <button type="button" className={styles.match} onClick={() => setWhyOpen(true)} aria-label={`Match ${Math.round(selected.score)}. Why this pick`}>
          <span>Match</span>
          <b className="at-numeral">{Math.round(selected.score)}</b>
        </button>
      </div>

      <Sheet open={whyOpen} onOpenChange={setWhyOpen} title="Why this">
        <div className={styles.why}>
          <p className="at-body">Fit scores use your collection and context. {recommendation.generation_mode === "ai" ? "AI compares eligible options using your supplied preferences and context." : "Personalized baseline ranking is active."} Evidence coverage measures available inputs, not statistical confidence.</p>
          <dl className={styles.scores}>
            {Object.entries(selected.score_components).map(([name, value]) => (
              <div key={name}><dt>{componentLabel(name)}</dt><dd className="at-tabular">{value}</dd></div>
            ))}
          </dl>
          {selected.warnings.length > 0 ? <ul className={styles.warnings}>{selected.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul> : null}
          <p className="at-caption">{evidenceLabel(selected.evidence_coverage)} · {recommendation.algorithm_version}</p>
        </div>
      </Sheet>

      <Sheet
        open={wearOpen}
        onOpenChange={setWearOpen}
        title={`Wear ${fragrance.name}`}
        footer={
          <div className={styles.sheetActions}>
            <Button type="submit" form={`${formId}-wear`} disabled={pending || !sprayValid}>{pending ? "Saving…" : "Log wear"}</Button>
            <Button variant="text" onClick={() => setWearOpen(false)}>Cancel</Button>
          </div>
        }
      >
        <form id={`${formId}-wear`} className={styles.wearForm} onSubmit={(event) => { event.preventDefault(); if (sprayValid) logWear(); }}>
          <Field label="Sprays" htmlFor={`${formId}-sprays`}>
            <Stepper id={`${formId}-sprays`} label="Sprays" min={1} max={30} value={sprays} onChange={setSprays} />
          </Field>
          <Field label="Occasion" htmlFor={`${formId}-occasion`}>
            <Select id={`${formId}-occasion`} value={occasion} onChange={(event) => setOccasion(event.target.value as Occasion | "")}>
              <option value="">No occasion</option>
              {OCCASIONS.map((value) => <option key={value} value={value}>{OCCASION_NAMES[value]}</option>)}
            </Select>
          </Field>
          <Field label="Setting" htmlFor={`${formId}-setting`}>
            <TextInput id={`${formId}-setting`} maxLength={40} value={setting} onChange={(event) => setSetting(event.target.value)} />
          </Field>
          <Field label="Private note (optional)" htmlFor={`${formId}-note`}>
            <TextInput id={`${formId}-note`} maxLength={2000} value={note} onChange={(event) => setNote(event.target.value)} />
          </Field>
          {error ? <p className={styles.error} role="alert">{error}</p> : null}
        </form>
      </Sheet>
    </section>
  );
}

export function HeroSkeleton() {
  return (
    <div className={styles.skeleton} aria-hidden="true">
      <div className={styles.skeletonCopy}>
        <span className="at-skeleton" style={{ width: 180, height: 32 }} />
        <span className="at-skeleton" style={{ width: "70%", height: 64 }} />
        <span className="at-skeleton" style={{ width: "85%", height: 18 }} />
        <span className="at-skeleton" style={{ width: 260, height: 44 }} />
      </div>
      <span className={cn("at-skeleton", styles.skeletonPlate)} />
    </div>
  );
}

