"use client";

import Link from "next/link";
import { useCallback, useRef, useState, useTransition, type FormEvent } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { toast } from "sonner";
import { ArrowDown, ArrowUp, Plus, Sparkles, X } from "lucide-react";
import { SurfaceOptions } from "@/features/recommendations/surface-options";
import { CatalogImage } from "@/components/catalog-image";
import { ExperienceBackdrop } from "@/components/shared/experience";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { motionTokens } from "@/lib/motion";
import {
  deleteLayerStack,
  evaluateLayerStack,
  getLayeringIntelligence,
  getLayerStackHistory,
  logLayerStackWear,
  rateLayerStackWear,
  renameLayerStack,
  saveLayerStack,
} from "@/lib/server/layering-actions";
import type { FragranceSummary } from "@/types/api";
import type {
  LayeringGoal,
  LayeringIntelligencePage,
  LayeringStackSuggestion,
  LayeringStackWear,
  SavedLayeringStack,
  StackMode,
} from "@/types/layering";
import styles from "./layering-lab.module.css";
import { LayeringStudioCanvas } from "./layering-studio-canvas";

const modes: StackMode[] = ["safe", "balanced", "contrast", "experimental"];
const goals: Record<LayeringGoal, string> = {
  fresher: "Make it fresher",
  warmer: "Make it warmer",
  sweeter: "Make it sweeter",
  darker: "Make it darker",
  cleaner: "Make it cleaner",
  softer: "Soften it",
  more_projection: "Boost projection",
  more_intimate: "Make it more intimate",
  daytime: "Daytime",
  evening: "Evening",
  spring: "Spring",
  summer: "Summer",
  fall: "Fall",
  winter: "Winter",
};
const percent = (value: number) => `${Math.round(value * 100)}%`;
const scoreOutOf100 = (value: number) => `${Math.round(value * 100)} out of 100`;
const roleLabel = (role: "anchor" | "bridge" | "accent") =>
  role === "anchor"
    ? "Your main scent"
    : role === "bridge"
      ? "Ties them together"
      : "Adds a twist";
const stackKey = (stack: LayeringStackSuggestion) =>
  stack.items.map((item) => item.fragrance.id).join(":");

type StudioDraft = {
  id: string;
  stackIds: string[];
  mode: StackMode;
  goal: LayeringGoal | null;
  evaluation: LayeringStackSuggestion;
  source: "custom" | "saved";
};

export function LayeringLab({
  owned,
  initialIntelligence,
  initialA,
  initialStack,
}: {
  owned: FragranceSummary[];
  initialIntelligence: LayeringIntelligencePage;
  initialA?: string;
  initialStack?: LayeringStackSuggestion;
}) {
  const [anchor, setAnchor] = useState(
    initialA ??
      initialIntelligence.suggestions[0]?.items[0].fragrance.id ??
      owned[0]?.id ??
      "",
  );
  const [mode, setMode] = useState<StackMode>(initialStack?.mode ?? "balanced");
  const [goal, setGoal] = useState<LayeringGoal | null>(
    initialStack?.goal ?? null,
  );
  const [intelligence, setIntelligence] = useState(initialIntelligence);
  const [saved, setSaved] = useState(initialIntelligence.saved);
  const [stackIds, setStackIds] = useState<string[]>(
    initialStack?.items.map((item) => item.fragrance.id) ?? [],
  );
  const [evaluation, setEvaluation] = useState<LayeringStackSuggestion | null>(
    initialStack ?? null,
  );
  const [pending, startTransition] = useTransition();
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState<LayeringStackSuggestion | null>(null);
  const [renaming, setRenaming] = useState<SavedLayeringStack | null>(null);
  const [name, setName] = useState("");
  const [wearTarget, setWearTarget] = useState<SavedLayeringStack | null>(null);
  const [rating, setRating] = useState("");
  const [notes, setNotes] = useState("");
  const [history, setHistory] = useState<{
    stack: SavedLayeringStack;
    wears: LayeringStackWear[];
  } | null>(null);
  const [detail, setDetail] = useState<LayeringStackSuggestion | null>(null);
  const [collectionQuery, setCollectionQuery] = useState("");
  const [deleting, setDeleting] = useState<SavedLayeringStack | null>(null);
  const [replacementCandidate, setReplacementCandidate] = useState<string | null>(null);
  const [replacementTarget, setReplacementTarget] = useState<string | null>(null);
  const [focusedBottleId, setFocusedBottleId] = useState<string | null>(null);
  const draftSequence = useRef(initialStack ? 1 : 0);
  const [drafts, setDrafts] = useState<StudioDraft[]>(() =>
    initialStack
      ? [{
          id: "draft-1",
          stackIds: initialStack.items.map((item) => item.fragrance.id),
          mode: initialStack.mode,
          goal: initialStack.goal ?? null,
          evaluation: initialStack,
          source: "custom",
        }]
      : [],
  );
  const [activeDraftId, setActiveDraftId] = useState<string | null>(
    initialStack ? "draft-1" : null,
  );
  const manualSelection = useRef(Boolean(initialStack));
  const requestVersion = useRef(0);
  const selectSurprise = useCallback((choice: import("@/types/api").DiscoveryResult | LayeringStackSuggestion) => {
    if (!("items" in choice))return;
    requestVersion.current++;setStackIds([]);setEvaluation(null);setAnchor(choice.items[0].fragrance.id);
    setReplacementCandidate(null);setReplacementTarget(null);setFocusedBottleId(null);
    setIntelligence(previous=>({...previous,suggestions:[choice,...previous.suggestions.filter(item=>stackKey(item)!==stackKey(choice))]}));
  },[]);
  const selectRestoredSurprise = useCallback((choice: import("@/types/api").DiscoveryResult | LayeringStackSuggestion) => {
    if (!manualSelection.current) selectSurprise(choice);
  }, [selectSurprise]);
  const reducedMotion = useReducedMotion();
  const selectedAnchor = owned.find((item) => item.id === anchor);
  const visibleOwned = owned.filter((item) =>
    `${item.name} ${item.brand.name}`.toLowerCase().includes(collectionQuery.trim().toLowerCase()),
  );
  const currentEvaluation = evaluation && evaluation.mode === mode && (evaluation.goal ?? null) === goal && evaluation.items.map((item) => item.fragrance.id).join(":") === stackIds.join(":") ? evaluation : null;
  const composition = !pending ? stackIds.length ? currentEvaluation : intelligence.suggestions.find((stack) => stack.items[0]?.fragrance.id === anchor && stack.mode === mode && (stack.goal ?? null) === goal) : undefined;
  const compositionItems = composition?.items ?? (stackIds.length ? stackIds : [anchor]).flatMap((id, index) => {
    const fragrance = owned.find((item) => item.id === id);
    return fragrance ? [{ fragrance, role: index === 0 ? "anchor" : "accent", suggested_sprays: null }] : [];
  });

  function run(action: () => Promise<void>) {
    setError("");
    startTransition(async () => {
      try {
        await action();
      } catch {
        setError("ScentIQ could not complete that request. Please try again.");
        toast.error("Could not update your layering lab");
      }
    });
  }
  function suggest(
    nextAnchor: string | undefined,
    nextMode: StackMode,
    nextGoal: LayeringGoal | null,
  ) {
    setReplacementCandidate(null);
    setReplacementTarget(null);
    setFocusedBottleId(null);
    const version = ++requestVersion.current;
    run(async () => {
      const next = await getLayeringIntelligence({
        anchorId: nextAnchor,
        mode: nextMode,
        goal: nextGoal,
      });
      if (version === requestVersion.current) setIntelligence(next);
    });
  }
  function evaluateSelection(
    ids: string[],
    nextMode: StackMode = mode,
    nextGoal: LayeringGoal | null = goal,
  ) {
    setEvaluation(null);
    setReplacementCandidate(null);
    setReplacementTarget(null);
    const version = ++requestVersion.current;
    if (ids.length < 2) return;
    run(async () => {
      const result = await evaluateLayerStack(ids, nextMode, nextGoal);
      if (version === requestVersion.current) {
        setEvaluation(result);
        retainEvaluatedDraft(ids, nextMode, nextGoal, result);
      }
    });
  }
  function retainEvaluatedDraft(
    ids: string[],
    nextMode: StackMode,
    nextGoal: LayeringGoal | null,
    result: LayeringStackSuggestion,
  ) {
    const draftId = activeDraftId ?? `draft-${++draftSequence.current}`;
    if (!activeDraftId) setActiveDraftId(draftId);
    const existing = drafts.find((item) => item.id === draftId);
    const nextDraft: StudioDraft = {
      id: draftId,
      stackIds: ids,
      mode: nextMode,
      goal: nextGoal,
      evaluation: result,
      source: existing?.source ?? "custom",
    };
    setDrafts((items) => [
      ...items.filter((item) => item.id !== draftId),
      nextDraft,
    ]);
  }
  function startNewBlend() {
    requestVersion.current++;
    manualSelection.current = true;
    setActiveDraftId(null);
    setStackIds([]);
    setEvaluation(null);
    setReplacementCandidate(null);
    setReplacementTarget(null);
    setFocusedBottleId(null);
  }
  function openDraft(draft: StudioDraft) {
    requestVersion.current++;
    manualSelection.current = true;
    setActiveDraftId(draft.id);
    setStackIds(draft.stackIds);
    setMode(draft.mode);
    setGoal(draft.goal);
    setEvaluation(draft.evaluation);
    setAnchor(draft.stackIds[0] ?? anchor);
    setReplacementCandidate(null);
    setReplacementTarget(null);
    setFocusedBottleId(null);
  }
  function updateStack(ids: string[]) {
    manualSelection.current = true;
    setStackIds(ids);
    evaluateSelection(ids);
  }
  function adoptComposition(stack: LayeringStackSuggestion, source: StudioDraft["source"] = "custom", forceNew = false) {
    requestVersion.current++;
    manualSelection.current = true;
    const ids = stack.items.map((item) => item.fragrance.id);
    const active = drafts.find((item) => item.id === activeDraftId);
    const sameActive = !forceNew && active && stackKey(active.evaluation) === stackKey(stack);
    const draftId = sameActive ? active.id : `draft-${++draftSequence.current}`;
    setDrafts((items) => [
      ...items.filter((item) => item.id !== draftId),
      {id:draftId, stackIds:ids, mode:stack.mode, goal:stack.goal ?? null, evaluation:stack, source},
    ]);
    setActiveDraftId(draftId);
    setStackIds(ids);
    setEvaluation(stack);
    setMode(stack.mode);
    setGoal(stack.goal ?? null);
    setAnchor(stack.items[0].fragrance.id);
    setReplacementCandidate(null);
    setReplacementTarget(null);
    setFocusedBottleId(null);
  }
  function edit(stack: LayeringStackSuggestion, source: StudioDraft["source"] = "custom") {
    adoptComposition(stack, source, source === "saved");
    focusBuilder();
  }
  function focusBuilder() {
    requestAnimationFrame(() => {
      const builder = document.getElementById("layer-stack-builder");
      builder?.scrollIntoView?.({behavior: reducedMotion ? "instant" : "smooth", block:"start"});
      builder?.focus({preventScroll:true});
    });
  }
  function openSave(stack: LayeringStackSuggestion) {
    adoptComposition(stack);
    setName("");
    setSaving(stack);
  }
  function confirmSaved(event: FormEvent) {
    event.preventDefault();
    run(async () => {
      if (renaming) {
        const updated = await renameLayerStack(renaming.id, name);
        setSaved((items) =>
          items.map((item) => (item.id === updated.id ? updated : item)),
        );
        setRenaming(null);
      } else if (saving) {
        const result = await saveLayerStack(
          saving.items.map((item) => item.fragrance.id),
          saving.mode,
          saving.goal ?? null,
          name,
        );
        setSaved((items) => [result, ...items]);
        if (activeDraftId) setDrafts((items) => items.map((item) => item.id === activeDraftId ? {...item, source:"saved"} : item));
        setSaving(null);
      }
      setMessage("Combination saved");
      toast.success("Combination saved");
    });
  }
  function openWear(stack: SavedLayeringStack) {
    setWearTarget(stack);
    setRating("");
    setNotes("");
  }
  function confirmWear(event: FormEvent) {
    event.preventDefault();
    if (!wearTarget) return;
    const target = wearTarget;
    run(async () => {
      const wear = await logLayerStackWear(
        target.id,
        rating ? Number(rating) : null,
        notes,
      );
      const wears = await getLayerStackHistory(target.id);
      const rated = wears.filter((item) => item.rating !== null);
      setSaved((items) =>
        items.map((item) =>
          item.id === target.id
            ? {
                ...item,
                last_worn_at: wear.worn_at,
                wear_count: wears.length,
                average_rating: rated.length
                  ? rated.reduce(
                      (total, entry) => total + (entry.rating ?? 0),
                      0,
                    ) / rated.length
                  : null,
              }
            : item,
        ),
      );
      setWearTarget(null);
      setMessage("Wear logged");
      toast.success("Wear logged");
    });
  }

  if (owned.length < 2)
    return (
      <section className="page">
        <PageHeader
          eyebrow="Layer with intention"
          title="Layering Lab"
          description="Start with a scent you own."
        />
        <Card>
          <CardContent className="empty-panel">
            <h2>Add at least two owned fragrances</h2>
            <p>Your collection supplies every anchor and supporting scent.</p>
            <Button asChild>
              <Link href="/collection">Open collection</Link>
            </Button>
          </CardContent>
        </Card>
      </section>
    );

  return (
    <section
      className={`page experience-page ${styles.experience}`}
      aria-label="Layering studio"
    >
      <ExperienceBackdrop tone="blend" />
      <header className={styles.studioHeader}>
        <div className={styles.studioBrand}>
          <span className={styles.brandMark}>S</span>
          <div><p>ScentIQ</p><h1>Layering Studio</h1></div>
        </div>
        <p className={styles.sessionMeta}>LIVE SESSION · {drafts.length} {drafts.length === 1 ? "BLEND" : "BLENDS"}</p>
        <Button variant="secondary" onClick={() => document.getElementById("saved-blends")?.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth" })}>My blends</Button>
      </header>
      {error ? <p role="alert">{error}</p> : null}
      {message ? <p role="status">{message}</p> : null}
      <section className={styles.composition} aria-label="Fragrance composition" aria-busy={pending}>
        <div className={styles.compositionCopy} role="region" aria-label="ScentIQ read">
          <p className="eyebrow">ScentIQ read</p>
          <h2>{composition ? composition.verdict : <>A scent that is<br />uniquely yours.</>}</h2>
          <p>{composition ? composition.explanation.why_they_fit[0] ?? "Explore the recorded notes behind this combination." : stackIds.length ? "Your composition is ready to explore. Adjust the ingredients in the stack builder to evaluate the recorded evidence." : "Choose your anchor and discover a new dimension in the fragrances you already own."}</p>
          <div className={styles.compositionStats}>
            <div><strong>{composition ? scoreOutOf100(composition.score) : "—"}</strong><span>Blend guidance</span></div>
            <div><strong>{composition ? composition.total_sprays : "—"}</strong><span>Starting sprays</span></div>
            <div><strong>{composition ? composition.evidence_summary : "—"}</strong><span>Information confidence</span></div>
          </div>
          <Button disabled={pending} onClick={() => { if (composition) edit(composition); else { if (!stackIds.length) { manualSelection.current = true; setStackIds([anchor]); setEvaluation(null); } focusBuilder(); } }}><Sparkles size={16} />{composition ? "Refine this blend" : stackIds.length ? "Continue composing" : "Compose a blend"}</Button>
          <p className="data-note">{pending ? "Comparing your fragrances…" : composition ? `Guidance, not a guarantee · ${composition.items.length}-scent composition` : "Your collection is the palette."}</p>
        </div>
        <LayeringStudioCanvas
          items={compositionItems}
          composition={composition}
          pending={pending}
          reducedMotion={reducedMotion}
          focusedId={focusedBottleId}
          onFocus={(id) => {
            if (!stackIds.length && composition) adoptComposition(composition);
            setFocusedBottleId(id);
          }}
          onMove={(id, direction) => {
            const index = stackIds.indexOf(id);
            const target = index + direction;
            if (index < 0 || target < 0 || target >= stackIds.length) return;
            const next = [...stackIds];
            [next[index], next[target]] = [next[target], next[index]];
            setFocusedBottleId(id);
            updateStack(next);
          }}
          onRemove={(id) => {
            setFocusedBottleId(null);
            updateStack(stackIds.filter((value) => value !== id));
          }}
          onReplace={(id) => {
            if (!stackIds.includes(id)) return;
            setReplacementCandidate(null);
            setReplacementTarget(id);
            document.getElementById("fragrance-shelf")?.scrollIntoView({behavior: reducedMotion ? "auto" : "smooth", block:"nearest"});
          }}
          onAdd={() => {
            if (!stackIds.length && composition) adoptComposition(composition);
            setFocusedBottleId(null);
            document.getElementById("fragrance-shelf")?.scrollIntoView({behavior: reducedMotion ? "auto" : "smooth", block:"nearest"});
          }}
        />
      </section>
      <AnimatePresence mode="wait" initial={false}>
      {composition ? (
        <motion.section
          key={`${stackKey(composition)}:${composition.mode}:${composition.goal ?? "balanced"}`}
          className={styles.resultStory}
          aria-label="Blend explanation"
          initial={reducedMotion ? false : "hidden"}
          animate="visible"
          exit={reducedMotion ? undefined : "hidden"}
          variants={{
            hidden: { opacity: 0 },
            visible: { opacity: 1, transition: reducedMotion ? { duration: 0 } : { staggerChildren: 0.07 } },
          }}
        >
          {[
            ["Why they fit", composition.explanation.why_they_fit],
            ["What changes", composition.explanation.what_changes],
            ["Watch out for", composition.explanation.watch_out_for],
          ].map(([heading, lines]) => (
            <motion.div
              key={heading as string}
              variants={reducedMotion ? undefined : { hidden: { opacity: 0, y: 12 }, visible: { opacity: 1, y: 0, transition: motionTokens.panel } }}
            >
              <h2>{heading}</h2>
              {(lines as string[]).map((line) => <p key={line}>{line}</p>)}
            </motion.div>
          ))}
        </motion.section>
      ) : null}
      </AnimatePresence>
      <Card className={styles.directionPanel}>
        <CardContent>
          <p className="eyebrow">Blend direction</p>
          <h2 className="serif">Build a scent with a point of view.</h2>
          <p>Choose the feeling, set your appetite for contrast, then compose from your shelf.</p>
          <section id="fragrance-shelf" aria-label="Your fragrance shelf" className={styles.shelfSection}>
          <div className={styles.shelfHeading}><h3>Your fragrance shelf</h3><span>Tap to add · swipe to explore</span></div>
          <label className={styles.searchLabel}>
            Search your collection
            <input
              className="input"
              type="search"
              value={collectionQuery}
              onChange={(event) => setCollectionQuery(event.target.value)}
            />
          </label>
          <div className={styles.picker} aria-label="Choose fragrances">
            {visibleOwned.map((item) => (
              <button
                type="button"
                key={item.id}
                className={styles.scentChoice}
                aria-label={stackIds.includes(item.id)
                  ? `${item.name} is in this blend`
                  : replacementTarget
                    ? `Replace ${owned.find((value) => value.id === replacementTarget)?.name ?? "selected fragrance"} with ${item.name}`
                    : `Add ${item.name}`}
                aria-pressed={stackIds.includes(item.id)}
                disabled={pending}
                onClick={() => {
                  manualSelection.current = true;
                  if (replacementTarget) {
                    if (stackIds.includes(item.id) || !stackIds.includes(replacementTarget)) return;
                    const next = stackIds.map((value) => value === replacementTarget ? item.id : value);
                    setReplacementTarget(null);
                    setFocusedBottleId(item.id);
                    updateStack(next);
                    return;
                  }
                  if (stackIds.includes(item.id)) return;
                  if (stackIds.length >= 3) {
                    setReplacementCandidate(item.id);
                    return;
                  }
                  const next = stackIds.length ? [...stackIds, item.id] : [item.id];
                  setAnchor(next[0]);
                  updateStack(next);
                }}
              >
                <CatalogImage
                  id={item.id}
                  name={item.name}
                  brand={item.brand.name}
                  imageUrl={item.image_url}
                  className={styles.smallImage}
                />
                <strong>{item.name}</strong>
                <span>{item.brand.name}</span>
              </button>
            ))}
          </div>
          {replacementCandidate ? (
            <section className={styles.replaceTray} aria-label="Replace a fragrance">
              <div><strong>Canvas full</strong><span>Choose what {owned.find((item) => item.id === replacementCandidate)?.name} should replace.</span></div>
              {stackIds.map((id) => {
                const item = owned.find((fragrance) => fragrance.id === id);
                return item ? (
                  <Button key={id} variant="secondary" aria-label={`Replace ${item.name}`} onClick={() => {
                    if (!replacementCandidate || stackIds.includes(replacementCandidate) || !stackIds.includes(id)) {
                      setReplacementCandidate(null);
                      return;
                    }
                    const next = stackIds.map((value) => value === id ? replacementCandidate : value);
                    setReplacementCandidate(null);
                    updateStack(next);
                  }}>{item.name}</Button>
                ) : null;
              })}
              <Button variant="ghost" onClick={() => setReplacementCandidate(null)}>Cancel</Button>
            </section>
          ) : null}
          </section>
          {selectedAnchor ? (
            <div className={styles.anchorSummary}>
              <Badge>Anchor</Badge>
              <strong>{selectedAnchor.name}</strong>
              <span>
                {selectedAnchor.top_accords.join(" · ") ||
                  "Profile not recorded"}
              </span>
              <span>
                Projection: {selectedAnchor.projection_level ?? "not recorded"}{" "}
                · Longevity: {selectedAnchor.longevity_score ?? "not recorded"}
              </span>
            </div>
          ) : null}
          <div className={styles.controls} aria-label="Layer toward a goal">
            <Button
              variant={goal === null ? "primary" : "secondary"}
              onClick={() => {
                setGoal(null);
                if (stackIds.length >= 2) evaluateSelection(stackIds, mode, null);
                else suggest(anchor, mode, null);
              }}
            >
              Keep it balanced
            </Button>
            {intelligence.supported_goals.map((item) => (
              <Button
                key={item}
                variant={goal === item ? "primary" : "secondary"}
                onClick={() => {
                  setGoal(item);
                  if (stackIds.length >= 2) evaluateSelection(stackIds, mode, item);
                  else suggest(anchor, mode, item);
                }}
              >
                {goals[item]}
              </Button>
            ))}
          </div>
          <h3>How adventurous?</h3>
          <div className={styles.controls} aria-label="How adventurous">
            {modes.map((item) => (
              <Button
                key={item}
                variant={mode === item ? "primary" : "ghost"}
                disabled={pending}
                onClick={() => {
                  setMode(item);
                  if (stackIds.length >= 2) evaluateSelection(stackIds, item, goal);
                  else suggest(anchor, item, goal);
                }}
              >
                {item}
              </Button>
            ))}
            <SurfaceOptions key={`${mode}:${goal}`} surface="layering" parameters={{mode,goal}} onChoice={selectSurprise} onRestoreChoice={selectRestoredSurprise} restore={!initialA && !initialStack && stackIds.length === 0} enabled={owned.length >= 2} choiceVersion={requestVersion.current}/>
            <Button
              variant="secondary"
              disabled={pending}
              onClick={() => {
                setStackIds([anchor]);
                setEvaluation(null);
                focusBuilder();
              }}
            >
              Build a custom stack
            </Button>
          </div>
        </CardContent>
      </Card>
      <div aria-live="polite">
        {pending ? <p>Comparing your owned fragrances…</p> : null}
      </div>
      <section aria-label="Session blends">
        <h2 className="serif">Session blends</h2>
        <div className={`${styles.controls} ${styles.sessionList}`}>
          <Button variant="secondary" onClick={startNewBlend}>New blend</Button>
          <AnimatePresence initial={false}>
          {drafts.map((draft) => (
            <motion.div
              key={draft.id}
              layout={!reducedMotion}
              className={styles.sessionEcho}
              initial={reducedMotion ? false : { opacity: 0, scale: 0.88, x: -10 }}
              animate={{ opacity: 1, scale: 1, x: 0 }}
              exit={reducedMotion ? undefined : { opacity: 0, scale: 0.92 }}
              transition={reducedMotion ? { duration: 0 } : motionTokens.panel}
            >
              <Button
                variant={draft.id === activeDraftId ? "primary" : "ghost"}
                aria-label={`${draft.evaluation.verdict} · ${Math.round(draft.evaluation.score * 100)}`}
                aria-current={draft.id === activeDraftId ? "true" : undefined}
                onClick={() => openDraft(draft)}
              >
                {draft.evaluation.verdict} · {Math.round(draft.evaluation.score * 100)}
              </Button>
            </motion.div>
          ))}
          </AnimatePresence>
        </div>
      </section>
      <section aria-label="Ranked layering suggestions">
        <h2 className="serif">Supporting scents, ranked for you</h2>
        <div className={styles.suggestions}>
          {intelligence.suggestions.map((stack) => (
            <Card key={stackKey(stack)}>
              <CardContent>
                <div className={styles.thumbnails}>
                  {stack.items.map((item) => (
                    <div key={item.fragrance.id}>
                      <CatalogImage
                        id={item.fragrance.id}
                        name={item.fragrance.name}
                        brand={item.fragrance.brand.name}
                        imageUrl={item.fragrance.image_url ?? null}
                        className={styles.smallImage}
                      />
                      <Badge>{roleLabel(item.role)}</Badge>
                      <strong>{item.fragrance.name}</strong>
                    </div>
                  ))}
                </div>
                <p>
                  <strong>{stack.verdict}</strong> · {scoreOutOf100(stack.score)} ·{" "}
                  {stack.items.length === 3 ? "Three-scent stack" : "Pair"}
                </p>
                <p>{stack.explanation.why_they_fit[0]}</p>
                <p>
                  {stack.total_sprays} sprays ·{" "}
                  {stack.items
                    .map(
                      (item) =>
                        `${item.fragrance.name} ${item.suggested_sprays}`,
                    )
                    .join(" + ")}
                </p>
                <p className="data-note">
                  {stack.evidence_summary}
                </p>
                <div className={styles.controls}>
                  <Button variant="secondary" disabled={pending} onClick={() => edit(stack)}>
                    Try / edit stack
                  </Button>
                  <Button disabled={pending} onClick={() => openSave(stack)}>
                    Save combination
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
        {!intelligence.suggestions.length && !pending ? (
          <p>
            Not enough owned profile data to suggest a combination yet. Build a
            custom stack to inspect the available evidence.
          </p>
        ) : null}
      </section>
      {stackIds.length ? (
        <section id="layer-stack-builder" tabIndex={-1} aria-label="Stack builder" className={styles.builder}>
          <h2 className="serif">Smart stack builder</h2>
          <p>
            Move a fragrance earlier to make it the anchor. Add up to two
            supporting scents.
          </p>
          <div className={styles.stackItems}>
            {stackIds.map((id, index) => {
              const item = owned.find((scent) => scent.id === id);
              if (!item) return null;
              const scored = evaluation?.items.find(
                (value) => value.fragrance.id === id,
              );
              return (
                <motion.div
                  key={id}
                  layout={!reducedMotion}
                  transition={motionTokens.standard}
                  className={styles.stackItem}
                  data-testid="stack-item"
                >
                  <CatalogImage
                    id={id}
                    name={item.name}
                    brand={item.brand.name}
                    imageUrl={item.image_url}
                    className={styles.smallImage}
                  />
                  <Badge>
                    {roleLabel(index === 0 ? "anchor" : (scored?.role ?? "accent"))}
                  </Badge>
                  <strong>{item.name}</strong>
                  <div className={styles.controls}>
                    <Button
                      variant="ghost"
                      aria-label={`Move ${item.name} earlier`}
                      disabled={index === 0 || pending}
                      onClick={() => {
                        const next = [...stackIds];
                        [next[index - 1], next[index]] = [
                          next[index],
                          next[index - 1],
                        ];
                        updateStack(next);
                      }}
                    >
                      <ArrowUp size={16} />
                    </Button>
                    <Button
                      variant="ghost"
                      aria-label={`Move ${item.name} later`}
                      disabled={index === stackIds.length - 1 || pending}
                      onClick={() => {
                        const next = [...stackIds];
                        [next[index + 1], next[index]] = [
                          next[index],
                          next[index + 1],
                        ];
                        updateStack(next);
                      }}
                    >
                      <ArrowDown size={16} />
                    </Button>
                    <Button
                      variant="ghost"
                      aria-label={`Remove ${item.name}`}
                      disabled={pending}
                      onClick={() =>
                        updateStack(stackIds.filter((value) => value !== id))
                      }
                    >
                      <X size={16} />
                    </Button>
                  </div>
                </motion.div>
              );
            })}
          </div>
          {stackIds.length < 3 ? (
            <div className={styles.controls}>
              {owned
                .filter((item) => !stackIds.includes(item.id))
                .map((item) => (
                  <Button
                    key={item.id}
                    disabled={pending}
                    variant="secondary"
                    aria-label={`Add ${item.name}`}
                    onClick={() => updateStack([...stackIds, item.id])}
                  >
                    <Plus size={16} />
                    {item.name}
                  </Button>
                ))}
            </div>
          ) : null}
          {evaluation && stackIds.length >= 2 ? (
            <Card>
              <CardContent>
                <h3>{evaluation.verdict}</h3>
                <p>{scoreOutOf100(evaluation.score)}</p>
                <Progress
                  value={Math.round(evaluation.score * 100)}
                  label="Whole-stack score"
                />
                <h3>Why they fit</h3>
                {evaluation.explanation.why_they_fit.map((line) => <p key={line}>{line}</p>)}
                <h3>What changes</h3>
                {evaluation.explanation.what_changes.map((line) => <p key={line}>{line}</p>)}
                <h3>How to apply it</h3>
                <ol>
                  {[...evaluation.items]
                    .sort((a, b) => a.application_order - b.application_order)
                    .map((item) => (
                      <li key={item.fragrance.id}>
                        <strong>{item.fragrance.name}</strong> ·{" "}
                        {item.suggested_sprays}{" "}
                        {item.suggested_sprays === 1 ? "spray" : "sprays"} ·{" "}
                        {roleLabel(item.role)}
                      </li>
                    ))}
                </ol>
                <p className="data-note">
                  Starting guidance: {evaluation.total_sprays} total sprays.
                  Adjust after trying a light application.
                </p>
                <h3>Best for</h3>
                <p>
                  {evaluation.best_contexts.join(" · ") ||
                    "Not enough season/context evidence yet"}
                </p>
                <h3>Watch out for</h3>
                {evaluation.explanation.watch_out_for.map((line) => <p key={line}>{line}</p>)}
                <div className={styles.controls}>
                  <Button
                    variant="secondary"
                    onClick={() => setDetail(evaluation)}
                  >
                    How ScentIQ scored this
                  </Button>
                  <Button
                    disabled={pending}
                    onClick={() => openSave(evaluation)}
                  >
                    Save this stack
                  </Button>
                  <Button
                    disabled={pending}
                    variant="secondary"
                    onClick={() => {
                      setName("");
                      setSaving(evaluation);
                      setMessage(
                        "Save your combination, then log its wear from Saved combinations.",
                      );
                    }}
                  >
                    Save and log a wear
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : (
            <p>Add another owned fragrance to evaluate your stack.</p>
          )}
        </section>
      ) : null}
      <section id="saved-blends" aria-label="Saved combinations">
        <h2 className="serif">Saved combinations</h2>
        <div className={styles.suggestions}>
          {saved.map((stack) => (
            <Card key={stack.id}>
              <CardContent>
                <h3>{stack.name}</h3>
                <div className={styles.thumbnails}>
                  {stack.suggestion.items.map((item) => (
                    <CatalogImage
                      key={item.fragrance.id}
                      id={item.fragrance.id}
                      name={item.fragrance.name}
                      brand={item.fragrance.brand.name}
                      imageUrl={item.fragrance.image_url ?? null}
                      className={styles.smallImage}
                    />
                  ))}
                </div>
                <p>
                  {stack.suggestion.items
                    .map((item) => item.fragrance.name)
                    .join(" + ")}
                </p>
                <p>
                  {stack.wear_count} wears ·{" "}
                  {stack.average_rating === null
                    ? "Not rated"
                    : `${stack.average_rating.toFixed(1)} / 5`}
                </p>
                <p>
                  Last worn:{" "}
                  {stack.last_worn_at
                    ? new Date(stack.last_worn_at).toLocaleDateString()
                    : "Not yet"}
                </p>
                <div className={styles.controls}>
                  <Button
                    aria-label={`Wear ${stack.name}`}
                    disabled={pending}
                    onClick={() => openWear(stack)}
                  >
                    Wear again
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => edit(stack.suggestion, "saved")}
                  >
                    Edit / duplicate
                  </Button>
                  <Button
                    variant="ghost"
                    aria-label={`Rename ${stack.name}`}
                    onClick={() => {
                      setName(stack.name);
                      setRenaming(stack);
                    }}
                  >
                    Rename
                  </Button>
                  <Button
                    variant="ghost"
                    aria-label={`History for ${stack.name}`}
                    disabled={pending}
                    onClick={() =>
                      run(async () =>
                        setHistory({
                          stack,
                          wears: await getLayerStackHistory(stack.id),
                        }),
                      )
                    }
                  >
                    History
                  </Button>
                  <Button
                    variant="ghost"
                    aria-label={`Delete ${stack.name}`}
                    onClick={() => setDeleting(stack)}
                  >
                    Delete
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
        {!saved.length ? (
          <p>Save a pair or three-scent stack to track how it works for you.</p>
        ) : null}
      </section>
      <Dialog
        open={Boolean(saving || renaming)}
        onOpenChange={(open) => {
          if (!open) {
            setSaving(null);
            setRenaming(null);
          }
        }}
      >
        <DialogContent
          title={renaming ? "Rename combination" : "Save combination"}
        >
          <form onSubmit={confirmSaved}>
            <label>
              Combination name
              <input
                className="input"
                value={name}
                onChange={(event) => setName(event.target.value)}
                required
                maxLength={120}
              />
            </label>
            <Button type="submit" disabled={pending || !name.trim()}>
              Save named combination
            </Button>
          </form>
        </DialogContent>
      </Dialog>
      <Dialog
        open={Boolean(wearTarget)}
        onOpenChange={(open) => {
          if (!open) setWearTarget(null);
        }}
      >
        <DialogContent title="Log a layered wear">
          <form onSubmit={confirmWear}>
            <p>{wearTarget?.name}</p>
            <label>
              Personal rating
              <select
                className="select"
                value={rating}
                onChange={(event) => setRating(event.target.value)}
              >
                <option value="">Rate later</option>
                {[1, 2, 3, 4, 5].map((value) => (
                  <option key={value} value={value}>
                    {value} / 5
                  </option>
                ))}
              </select>
            </label>
            <label>
              Wear notes
              <textarea
                className="input"
                value={notes}
                maxLength={2000}
                onChange={(event) => setNotes(event.target.value)}
              />
            </label>
            <Button type="submit" disabled={pending}>
              Log this wear
            </Button>
          </form>
        </DialogContent>
      </Dialog>
      <Dialog
        open={Boolean(detail)}
        onOpenChange={(open) => {
          if (!open) setDetail(null);
        }}
      >
        <DialogContent title="How ScentIQ scored this">
          <p>
            {percent(detail?.evidence_coverage ?? 0)} recorded evidence ·{" "}
            {detail?.algorithm_version}
          </p>
          <dl>
            {detail
              ? Object.entries(detail.score_components).map(
                  ([label, value]) => (
                    <div key={label}>
                      <dt>{label.replaceAll("_", " ")}</dt>
                      <dd>{percent(value)}</dd>
                    </div>
                  ),
                )
              : null}
          </dl>
          <p className="data-note">
            Recorded catalog overlap supports the evidence. Role, order, and
            spray guidance use deterministic rules.
          </p>
        </DialogContent>
      </Dialog>
      <Dialog
        open={Boolean(history)}
        onOpenChange={(open) => {
          if (!open) setHistory(null);
        }}
      >
        <DialogContent title="Layering history">
          <h3>{history?.stack.name}</h3>
          {history?.wears.length ? (
            history.wears.map((wear) => (
              <div key={wear.id}>
                <p>{new Date(wear.worn_at).toLocaleDateString()}</p>
                <p>{wear.notes}</p>
                <label>
                  Rate this wear
                  <select
                    className="select"
                    aria-label={`Rate wear ${wear.id}`}
                    value={wear.rating ?? ""}
                    disabled={pending}
                    onChange={(event) => {
                      const nextRating = Number(event.target.value);
                      if (!nextRating || !history) return;
                      const target = history;
                      run(async () => {
                        const updated = await rateLayerStackWear(
                          target.stack.id,
                          wear.id,
                          nextRating,
                        );
                        setHistory({
                          ...target,
                          wears: target.wears.map((entry) =>
                            entry.id === wear.id ? updated : entry,
                          ),
                        });
                        toast.success("Rating saved");
                      });
                    }}
                  >
                    <option value="">Not rated</option>
                    {[1, 2, 3, 4, 5].map((value) => (
                      <option key={value} value={value}>
                        {value} / 5
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            ))
          ) : (
            <p>No layered wears logged yet.</p>
          )}
        </DialogContent>
      </Dialog>
      <Dialog
        open={Boolean(deleting)}
        onOpenChange={(open) => {
          if (!open) setDeleting(null);
        }}
      >
        <DialogContent title="Delete combination">
          <p>
            Remove {deleting?.name} and its layering history? Individual
            fragrance wear logs stay in your rotation.
          </p>
          <Button
            disabled={pending}
            onClick={() => {
              if (!deleting) return;
              const id = deleting.id;
              run(async () => {
                await deleteLayerStack(id);
                setSaved((items) => items.filter((item) => item.id !== id));
                setDeleting(null);
                toast.success("Combination deleted");
              });
            }}
          >
            Delete saved combination
          </Button>
        </DialogContent>
      </Dialog>
    </section>
  );
}
