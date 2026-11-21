"use client";

import { useEffect, useMemo, useRef, useState, useTransition } from "react";
import { Button } from "@/components/ui/button";
import { surfaceChoice, type SurfaceChoice, type SurfaceChoiceInput } from "@/lib/server/surface-choice-actions";
import type { DiscoveryResult } from "@/types/api";
import type { LayeringStackSuggestion } from "@/types/layering";

type Props = {
  surface: "discovery" | "layering";
  parameters: Record<string, unknown>;
  onChoice: (choice: DiscoveryResult | LayeringStackSuggestion) => void;
  onRestoreChoice?: (choice: DiscoveryResult | LayeringStackSuggestion) => void;
  enabled?: boolean;
  restore?: boolean;
  choiceVersion?: number;
};

export function SurfaceOptions({ surface, parameters, onChoice, onRestoreChoice = onChoice, enabled = true, restore = true, choiceVersion = 0 }: Props) {
  const key = JSON.stringify(parameters);
  const stableParameters = useMemo(() => JSON.parse(key) as Record<string, unknown>, [key]);
  const [choice, setChoice] = useState<SurfaceChoice | null>(null);
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();
  const retry = useRef<SurfaceChoiceInput | null>(null);
  const latestChoiceVersion = useRef(choiceVersion);
  const mounted = useRef(true);

  useEffect(() => () => { mounted.current = false; }, []);
  useEffect(() => { latestChoiceVersion.current = choiceVersion; }, [choiceVersion]);

  useEffect(() => {
    if (!enabled || !restore) return;
    let active = true;
    startTransition(async () => {
      const result = await surfaceChoice(surface, {
        idempotency_key: crypto.randomUUID(),
        advance: false,
        parameters: stableParameters,
      });
      if (!active) return;
      if (result.ok) {
        setChoice(result.data);
        setError("");
        if (result.data.selected) onRestoreChoice(result.data.selected);
      } else setError(result.error);
    });
    return () => { active = false; };
  }, [surface, stableParameters, onRestoreChoice, enabled, restore]);

  function advance(reset = false) {
    if (!retry.current || Boolean(retry.current.reset) !== reset) {
      retry.current = {
        batch_id: choice?.batch_id,
        idempotency_key: crypto.randomUUID(),
        reset,
        advance: true,
        expected_candidate_id: choice?.candidate_id,
        parameters: stableParameters,
      };
    }
    const request = retry.current;
    const versionAtStart = choiceVersion;
    startTransition(async () => {
      const result = await surfaceChoice(surface, request);
      if (!mounted.current || latestChoiceVersion.current !== versionAtStart) {
        retry.current = null;
        return;
      }
      if (!result.ok) {
        setError(result.error);
        if (result.code === "batch_changed") {
          setChoice(null);
          retry.current = null;
        }
        return;
      }
      retry.current = null;
      setChoice(result.data);
      setError("");
      if (result.data.selected) onChoice(result.data.selected);
    });
  }

  if (!enabled) return null;
  return <div className="cluster">
    <Button disabled={pending || choice?.options_exhausted} variant="secondary" onClick={() => advance()}>
      {pending ? "Finding an option…" : surface === "discovery" ? "Another discovery" : "Surprise me"}
    </Button>
    {choice?.options_exhausted && <>
      <p role="status">You’ve seen all eligible options in this batch.</p>
      <Button disabled={pending} variant="ghost" onClick={() => advance(true)}>Start over</Button>
    </>}
    {error && <p role="alert">{error}</p>}
  </div>;
}
