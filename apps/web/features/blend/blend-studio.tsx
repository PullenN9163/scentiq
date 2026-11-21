"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { animate, motion, type PanInfo } from "motion/react";
import { ChevronLeft, Search, SlidersHorizontal } from "lucide-react";
import { useEffect, useMemo, useReducer, useRef, useState, useTransition } from "react";
import { toast } from "sonner";

import { Button } from "@/components/atelier/button";
import { Chip } from "@/components/atelier/chip";
import { centerOf, effectsReduced, playMist, resolveColor } from "@/components/atelier/mist";
import { Plate } from "@/components/atelier/plate";
import { plateFragrance } from "@/components/atelier/plate-fragrance";
import { SegmentedControl } from "@/components/atelier/segmented-control";
import { Sheet } from "@/components/atelier/sheet";
import { accordFor, accordVars, type AccordKey } from "@/lib/accord";
import { generateBlendName } from "@/lib/blend-names";
import { motionTokens } from "@/lib/motion";
import { recordEvents } from "@/lib/server/event-actions";
import { getLayeringIntelligence, logLayerStackWear, rateLayerStackWear, saveLayerStack } from "@/lib/server/layering-actions";
import { cn } from "@/lib/utils";
import type { CollectionItem, FragranceSummary } from "@/types/api";
import type { LayeringGoal, LayeringStackSuggestion, SavedLayeringStack, StackMode } from "@/types/layering";

import { RatingSheet, SaveSheet, VaultSheet } from "./blend-sheets";
import { GOAL_LABELS, MODES, MORE_GOALS, PRIMARY_GOALS, scoreOf } from "./blend-copy";
import { snapshotOfSaved } from "./blend-start";
import { blendReducer, initialBlend, sameBlend, suggestionMatches, type BlendStart } from "./blend-state";
import { CologneBottle } from "./cologne-bottle";
import { type FlaskLayer } from "./flask";
import { SprayZones } from "./spray-zones";
import { useBlendEvaluation } from "./use-blend-evaluation";
import styles from "./blend.module.css";

const UNDO_MS = 6000;
/** A drag shorter than this is a tap. */
const DRAG_SLOP_PX = 6;

type SaveMode = "save" | "wear";

/**
 * The Blend studio: a dark room, a glass flask, the member's owned bottles on
 * a shelf. Adding a bottle pours it in; the API's suggested spray split sets
 * the layer heights; the score and verdict react. Blends are saved, worn and
 * rated from here, and the cabinet lists the saved ones.
 */
export function BlendStudio({ owned, saved, supportedGoals, start }: { owned: CollectionItem[]; saved: SavedLayeringStack[]; supportedGoals?: LayeringGoal[]; start: BlendStart }) {
  const router = useRouter();
  const [state, dispatch] = useReducer(blendReducer, start, (value) => initialBlend(value));
  const { retry } = useBlendEvaluation(state, dispatch, Boolean(start.suggestion));
  const [moreGoals, setMoreGoals] = useState(false);
  const [whyOpen, setWhyOpen] = useState(false);
  const [tuneOpen, setTuneOpen] = useState(false);
  const [vaultOpen, setVaultOpen] = useState(false);
  const [saveMode, setSaveMode] = useState<SaveMode | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [rating, setRating] = useState<{ stackId: string; wearId: string } | null>(null);
  const [pulse, setPulse] = useState(0);
  const [undoVisible, setUndoVisible] = useState(false);
  const [query, setQuery] = useState("");
  const [surprising, startSurprise] = useTransition();
  const [committing, startCommit] = useTransition();
  const [ratingPending, startRating] = useTransition();
  const undoTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSurprise = useRef<string | null>(null);
  const pourTimers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const flaskRef = useRef<HTMLDivElement>(null);
  const atomizerRef = useRef<HTMLSpanElement>(null);
  const wearRef = useRef<HTMLButtonElement>(null);
  const roomRef = useRef<HTMLDivElement>(null);
  const shownRef = useRef<number | null>(null);
  const dragged = useRef(false);
  const [counting, setCounting] = useState<number | null>(null);

  const byId = useMemo(() => new Map<string, FragranceSummary>(owned.map((item) => [item.fragrance.id, item.fragrance])), [owned]);
  useEffect(() => () => { if (undoTimer.current) clearTimeout(undoTimer.current); pourTimers.current.forEach(clearTimeout); }, []);

  function changed() {
    setUndoVisible(true);
    if (undoTimer.current) clearTimeout(undoTimer.current);
    undoTimer.current = setTimeout(() => setUndoVisible(false), UNDO_MS);
  }
  const toggle = (id: string) => { dispatch({ type: "toggle", id }); changed(); };
  const setGoal = (goal: LayeringGoal) => {
    dispatch({ type: "goal", goal });
    changed();
    void recordEvents([{ event_type: "filter_select", subject_type: "ui", context: { goal: state.goal === goal ? "none" : goal, mode: state.mode } }]);
  };
  const setMode = (mode: StackMode) => {
    dispatch({ type: "mode", mode });
    changed();
    void recordEvents([{ event_type: "filter_select", subject_type: "ui", context: { mode, goal: state.goal ?? "none" } }]);
  };

  /** A bottle dropped on the flask is added; anywhere else it snaps back. */
  function dropOnFlask(id: string, point: PanInfo["point"]) {
    const box = flaskRef.current?.getBoundingClientRect();
    if (!box || state.ids.includes(id)) return;
    const inside = point.x >= box.left && point.x <= box.right && point.y >= box.top && point.y <= box.bottom;
    if (inside) { dispatch({ type: "add", id }); changed(); }
  }

  function surprise() {
    startSurprise(async () => {
      try {
        void recordEvents([{ event_type: "surprise_click", subject_type: "ui", context: { mode: state.mode, goal: state.goal ?? "none" } }]);
        // A fresh seed each time picks a different anchor and a weighted pick among the best blends.
        const page = await getLayeringIntelligence({ anchorId: undefined, mode: state.mode, goal: state.goal, surpriseSeed: Math.floor(Math.random() * 2_147_483_647) });
        const options = page.suggestions.filter((suggestion) => suggestion.items.every((item) => byId.has(item.fragrance.id)));
        const key = (suggestion: LayeringStackSuggestion) => suggestion.items.map((item) => item.fragrance.id).sort().join();
        const pick = options.find((suggestion) => key(suggestion) !== lastSurprise.current && key(suggestion) !== [...state.ids].sort().join()) ?? options.find((suggestion) => key(suggestion) !== lastSurprise.current);
        if (!pick) { toast("No new combination to suggest. Try another tilt."); return; }
        lastSurprise.current = key(pick);
        void recordEvents([{ event_type: "surprise_shown", subject_type: "stack", fragrance_ids: pick.items.map((item) => item.fragrance.id), context: { mode: pick.mode, goal: pick.goal ?? "none" } }]);
        const ids = [...pick.items].sort((a, b) => a.application_order - b.application_order).map((item) => item.fragrance.id);
        pourTimers.current.forEach(clearTimeout);
        dispatch({ type: "load", ids: [ids[0]], mode: pick.mode, goal: pick.goal ?? null });
        pourTimers.current = ids.slice(1).map((id, index) => setTimeout(() => dispatch({ type: "add", id }), 300 * (index + 1)));
        changed();
      } catch {
        toast.error("Could not find a combination right now. Try again.");
      }
    });
  }

  function done() {
    if (window.history.length > 1) router.back();
    else router.push("/dashboard");
  }

  const matches = suggestionMatches(state);
  const suggestion = matches ? state.suggestion : null;
  const items = suggestion ? [...suggestion.items].sort((a, b) => a.application_order - b.application_order) : null;
  const layers: FlaskLayer[] = items
    ? items.map((item) => ({ id: item.fragrance.id, accord: accordFor(item.fragrance), sprays: item.suggested_sprays }))
    : state.ids.flatMap((id) => { const fragrance = byId.get(id); return fragrance ? [{ id, accord: accordFor(fragrance), sprays: 1 }] : []; });
  const fill = state.ids.length === 1 ? 0.4 : layers.length ? 0.85 : 0;
  const glow = layers.map((layer) => `var(--chart-${layer.accord === "neutral" ? "musk" : layer.accord})`);
  const glowColor = glow.length === 0 ? "transparent" : glow.slice(1).reduce((mix, color) => `color-mix(in srgb, ${mix}, ${color})`, glow[0]);
  const notes = suggestion ? [...new Set([...suggestion.shared_notes, ...suggestion.bridge_signals])].slice(0, 3) : [];
  const goals = [...PRIMARY_GOALS, ...(moreGoals ? MORE_GOALS : [])].filter((goal) => !supportedGoals || supportedGoals.includes(goal));
  const lastName = state.lastAdded ? byId.get(state.lastAdded)?.name : null;
  const announcement = suggestion && lastName ? `Added ${lastName}. Score ${scoreOf(suggestion.score)}, ${suggestion.verdict}.` : "";
  const shelf = owned.filter((item) => !query.trim() || `${item.fragrance.name} ${item.fragrance.brand.name}`.toLowerCase().includes(query.trim().toLowerCase()));
  const lastAddedFragrance = state.lastAdded ? byId.get(state.lastAdded) : undefined;

  // The saved blend this flask matches, if any (by bottles, mode and tilt).
  const savedMatch = useMemo(() => saved.find((entry) => sameBlend(snapshotOfSaved(entry), state)) ?? null, [saved, state]);
  const savedId = savedMatch?.id ?? (state.savedId && saved.some((entry) => entry.id === state.savedId) ? state.savedId : null);
  const existing = savedMatch;

  // Each bottle added sprays a burst of mist from the atomizer into the flask.
  useEffect(() => {
    const id = state.lastAdded;
    const fragrance = id ? byId.get(id) : undefined;
    if (!fragrance || !atomizerRef.current || !flaskRef.current) return;
    const key = accordFor(fragrance);
    const color = resolveColor(flaskRef.current, `--chart-${key === "neutral" ? "musk" : key}`);
    void playMist({ from: centerOf(atomizerRef.current), to: centerOf(flaskRef.current), color, particles: 32 });
  }, [state.lastAdded, byId]);

  // Waves and bubbles stop drifting while the tab is hidden.
  useEffect(() => {
    const sync = () => roomRef.current?.setAttribute("data-paused", String(document.hidden));
    document.addEventListener("visibilitychange", sync);
    return () => document.removeEventListener("visibilitychange", sync);
  }, []);

  // The numeral counts to its new value; with reduced effects it simply changes.
  const target = suggestion ? scoreOf(suggestion.score) : null;
  useEffect(() => {
    if (target === null) return;
    if (effectsReduced()) { shownRef.current = target; return; }
    const from = shownRef.current ?? target;
    if (from === target) return;
    const controls = animate(from, target, {
      duration: 0.4,
      ease: "easeOut",
      onUpdate: (value) => { const rounded = Math.round(value); shownRef.current = rounded; setCounting(rounded); },
      onComplete: () => { shownRef.current = target; setCounting(null); },
    });
    return () => controls.stop();
  }, [target]);
  const numeral = counting ?? target;

  /** Mist from the wear button up into the flask, in the strongest accord's color. */
  function mistFromWear() {
    const from = wearRef.current;
    const flask = flaskRef.current;
    if (!from || !flask) return;
    const strongest: AccordKey = layers[layers.length - 1]?.accord ?? "neutral";
    const color = resolveColor(flask, `--chart-${strongest === "neutral" ? "musk" : strongest}`);
    void playMist({ from: centerOf(from), to: centerOf(flask), color, particles: 36 });
  }

  /** Logs a wear of a saved blend, then offers a rating. */
  function wearSaved(stackId: string) {
    startCommit(async () => {
      try {
        const wear = await logLayerStackWear(stackId, null, "");
        mistFromWear();
        toast.success("Blend worn");
        setRating({ stackId, wearId: wear.id });
        router.refresh();
      } catch {
        toast.error("That did not log. Try again.");
      }
    });
  }

  function onWear() {
    if (savedId) wearSaved(savedId);
    else { setSaveError(null); setSaveMode("wear"); }
  }

  /** Saves the flask (and wears it when asked). */
  function saveBlend(name: string, note: string, andWear: boolean) {
    startCommit(async () => {
      try {
        const entry = await saveLayerStack(state.ids, state.mode, state.goal, name, note || undefined);
        dispatch({ type: "saved", savedId: entry.id });
        void recordEvents([{ event_type: "stack_save", subject_type: "stack", fragrance_ids: state.ids, context: { mode: state.mode, goal: state.goal ?? "none" } }]);
        setPulse((count) => count + 1);
        setSaveMode(null);
        setSaveError(null);
        toast.success("Blend saved");
        router.refresh();
        if (andWear) {
          const wear = await logLayerStackWear(entry.id, null, "");
          mistFromWear();
          toast.success("Blend worn");
          setRating({ stackId: entry.id, wearId: wear.id });
          router.refresh();
        }
      } catch {
        setSaveError("That did not save. Try again.");
      }
    });
  }

  function rate(value: number) {
    if (!rating) return;
    const pending = rating;
    startRating(async () => {
      try {
        await rateLayerStackWear(pending.stackId, pending.wearId, value);
        toast.success("Rating saved");
        setRating(null);
        router.refresh();
      } catch {
        toast.error("That rating did not save. Try again.");
      }
    });
  }

  const controls = (
    <div className={styles.controls}>
      <div className={styles.controlGroup} role="group" aria-label="Tilt it">
        <span className={styles.controlLabel}>Tilt it</span>
        <div className={styles.chips}>
          {goals.map((goal) => <Chip key={goal} variant="choice" pressed={state.goal === goal} onClick={() => setGoal(goal)}>{GOAL_LABELS[goal]}</Chip>)}
          {!moreGoals ? <Chip variant="choice" pressed={false} onClick={() => setMoreGoals(true)}>More</Chip> : null}
        </div>
      </div>
      <div className={styles.controlGroup}>
        <span className={styles.controlLabel}>How adventurous</span>
        <SegmentedControl<StackMode> label="How adventurous" value={state.mode} onChange={setMode} segments={MODES} size="compact" />
      </div>
    </div>
  );

  if (owned.length < 2) {
    return (
      <div className={styles.room} data-theme="dark">
        <header className={styles.bar}><Button variant="text" onClick={done}><ChevronLeft aria-hidden="true" />Done</Button></header>
        <div className={styles.emptyRoom}>
          <h1 className="at-title">Add fragrances to your shelf to start blending</h1>
          <p className="at-caption">A blend needs at least two bottles you own.</p>
          <Button asChild variant="outline"><Link href="/collection">Open Collection</Link></Button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.room} data-theme="dark" ref={roomRef}>
      <header className={styles.bar}>
        <Button variant="text" onClick={done}><ChevronLeft aria-hidden="true" />Done</Button>
        <div className={styles.barActions}>
          <Button variant="outline" size="sm" onClick={() => setVaultOpen(true)}>Blends <span key={pulse} className={pulse ? styles.landed : undefined}>{saved.length}</span></Button>
          <Button variant="soft" size="sm" disabled={surprising} onClick={surprise}>{surprising ? "Finding…" : "Surprise me"}</Button>
          <Button size="sm" disabled={state.ids.length < 2 || committing} onClick={() => { setSaveError(null); setSaveMode("save"); }}>Save blend</Button>
        </div>
      </header>

      <div className={styles.stage}>
        <div className={styles.flaskArea} ref={flaskRef}>
          <span className={styles.glow} style={{ backgroundColor: glowColor }} aria-hidden="true" />
          <span ref={atomizerRef} className={styles.atomizer} aria-hidden="true" />
          {lastAddedFragrance ? (
            // The plate lifts from the shelf into the flask's neck, then fades.
            <motion.div key={`${state.lastAdded}:${state.ids.join()}`} className={styles.ghost} initial={{ y: 120, scale: 0.8 }} animate={{ y: 0, scale: 1 }} transition={motionTokens.springLively} aria-hidden="true">
              <Plate fragrance={plateFragrance(lastAddedFragrance)} accord={accordFor(lastAddedFragrance)} className={styles.ghostPlate} decorative compact />
            </motion.div>
          ) : null}
          <CologneBottle layers={layers} fill={fill} title={items ? items.map((item) => item.fragrance.name).join(" + ") : "Your blend"} percent={target} sprayKey={state.lastAdded ? `${state.lastAdded}:${state.ids.length}` : ""} />
          {state.ids.length === 0 ? <p className={styles.prompt}>Tap or drag a bottle into the flask</p> : null}
          {state.ids.length === 1 ? <p className={styles.prompt}>Add a second bottle</p> : null}
        </div>

        <section className={styles.reading} aria-label="Blend reading">
          {suggestion ? (
            <>
              <p className={styles.numeral}><span className="at-tabular">{numeral}</span><span aria-hidden="true">%</span></p>
              <p className={styles.verdict}>{suggestion.verdict}</p>
            </>
          ) : state.ids.length >= 2 ? (
            <p className={cn(styles.verdict, styles.waiting)} aria-busy="true">Reading the blend…</p>
          ) : null}
          {items ? (
            <div className={styles.chips} aria-label="In the flask">
              {items.map((item) => <Chip key={item.fragrance.id} className={styles.strand} style={accordVars(accordFor(item.fragrance))}>{item.fragrance.name} · {item.suggested_sprays} {item.suggested_sprays === 1 ? "spray" : "sprays"}</Chip>)}
            </div>
          ) : null}
          {notes.length ? <div className={styles.chips} aria-label="Shared notes">{notes.map((note) => <Chip key={note} variant="note">{note}</Chip>)}</div> : null}
          {suggestion ? <Button variant="text" size="sm" onClick={() => setWhyOpen(true)}>Why it works</Button> : null}
          {suggestion ? <Button ref={wearRef} variant="primary" size="sm" disabled={committing} onClick={onWear}>{savedId ? "Wear this blend" : "Save and wear"}</Button> : null}
          {state.status === "error" ? (
            <p className={styles.error} role="alert">Could not read this blend. Try again. <Button variant="text" size="sm" onClick={retry}>Try again</Button></p>
          ) : null}
          {undoVisible && state.history.length > 0 ? <Button variant="text" size="sm" onClick={() => { dispatch({ type: "undo" }); setUndoVisible(false); }}>Undo</Button> : null}
          <Button variant="soft" size="sm" className={styles.tune} onClick={() => setTuneOpen(true)}><SlidersHorizontal aria-hidden="true" />Tune</Button>
        </section>

        <div className={styles.desktopControls}>{controls}</div>
      </div>

      <div className={styles.shelf}>
        {owned.length > 12 ? (
          <label className={styles.shelfSearch}>
            <Search aria-hidden="true" />
            <span className="sr-only">Find a bottle</span>
            <input type="search" value={query} placeholder="Find a bottle" onChange={(event) => setQuery(event.target.value)} />
          </label>
        ) : null}
        <ul className={styles.rail} aria-label="Your shelf">
          {shelf.map((item) => {
            const position = state.ids.indexOf(item.fragrance.id);
            const inFlask = position >= 0;
            return (
              <li key={item.id}>
                <motion.button
                  type="button"
                  className={cn(styles.bottle, inFlask && styles.inFlask)}
                  aria-pressed={inFlask}
                  aria-label={`${inFlask ? "Remove" : "Add"} ${item.fragrance.name}`}
                  drag
                  dragSnapToOrigin
                  dragElastic={0.6}
                  dragMomentum={false}
                  onPointerDown={() => { dragged.current = false; }}
                  onDragEnd={(_event, info) => {
                    dragged.current = Math.hypot(info.offset.x, info.offset.y) > DRAG_SLOP_PX;
                    if (dragged.current) dropOnFlask(item.fragrance.id, info.point);
                  }}
                  onClick={() => {
                    if (dragged.current) { dragged.current = false; return; }
                    toggle(item.fragrance.id);
                  }}
                  onKeyDown={(event) => {
                    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
                    event.preventDefault();
                    const sibling = (event.currentTarget.parentElement?.[event.key === "ArrowRight" ? "nextElementSibling" : "previousElementSibling"] as HTMLElement | null)?.querySelector("button");
                    sibling?.focus();
                  }}
                >
                  <Plate fragrance={plateFragrance(item.fragrance)} accord={accordFor(item.fragrance)} className={styles.bottlePlate} decorative compact sizes="96px" />
                  {inFlask ? <span className={styles.badge} aria-hidden="true">{position + 1}</span> : null}
                  <span className={styles.bottleName}>{item.fragrance.name}</span>
                </motion.button>
              </li>
            );
          })}
        </ul>
      </div>

      <div className="sr-only" role="status" aria-live="polite">{announcement}</div>

      <Sheet open={tuneOpen} onOpenChange={setTuneOpen} title="Tune" theme="dark">{controls}</Sheet>
      <Sheet open={whyOpen} onOpenChange={setWhyOpen} title="Why it works" theme="dark">
        {suggestion ? (
          <div className={styles.why}>
            <WhyList title="Why they fit" items={suggestion.explanation.why_they_fit} />
            <WhyList title="What changes" items={suggestion.explanation.what_changes} />
            {suggestion.items.some((item) => (item.zones ?? []).length > 0) ? (
              <section>
                <h3 className="at-subtitle">Where to spray</h3>
                <SprayZones stack={suggestion} />
              </section>
            ) : null}
            <WhyList title="Known pairings" items={suggestion.pairing_evidence ?? []} />
            <WhyList title="How your tilt shaped it" items={suggestion.filter_effects ?? []} />
            <WhyList title="Watch out for" items={[...suggestion.explanation.watch_out_for, ...suggestion.warnings]} />
            <p className="at-caption">{suggestion.evidence_summary}</p>
          </div>
        ) : null}
      </Sheet>
      <SaveSheet
        open={saveMode !== null}
        onOpenChange={(open) => { if (!open) setSaveMode(null); }}
        title={saveMode === "wear" ? "Save and wear" : "Save blend"}
        submitLabel={saveMode === "wear" ? "Save and wear" : "Save blend"}
        suggestedName={generateBlendName(items ? items.map((item) => accordFor(item.fragrance)) : layers.map((layer) => layer.accord))}
        existing={saveMode === "save" ? existing : null}
        pending={committing}
        error={saveError}
        onSubmit={(name, note) => saveBlend(name, note, saveMode === "wear")}
        onOpenExisting={(id) => { setSaveMode(null); router.push(`/layering?saved=${id}`); }}
      />
      <RatingSheet open={rating !== null} onOpenChange={(open) => { if (!open) setRating(null); }} pending={ratingPending} onRate={rate} />
      <VaultSheet open={vaultOpen} onOpenChange={setVaultOpen} saved={saved} />
    </div>
  );
}

function WhyList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <section>
      <h3 className="at-subtitle">{title}</h3>
      <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul>
    </section>
  );
}
