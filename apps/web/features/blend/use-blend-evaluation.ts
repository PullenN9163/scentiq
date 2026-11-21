"use client";

import { useEffect, useRef, type Dispatch } from "react";

import { evaluateLayerStack } from "@/lib/server/layering-actions";

import type { BlendAction, BlendState } from "./blend-state";

export const EVALUATE_DELAY_MS = 250;

/**
 * Re-evaluates the flask 250ms after the last change, with two or more
 * bottles. Responses for an older request are ignored by the reducer.
 */
export function useBlendEvaluation(state: BlendState, dispatch: Dispatch<BlendAction>, skipFirst = false) {
  const counter = useRef(state.request);
  const skip = useRef(skipFirst);
  const key = `${state.ids.join(",")}|${state.mode}|${state.goal ?? ""}`;
  const { ids, mode, goal } = state;
  useEffect(() => {
    if (skip.current) { skip.current = false; return; }
    if (ids.length < 2) return;
    const request = ++counter.current;
    const timer = window.setTimeout(() => {
      dispatch({ type: "evaluating", request });
      evaluateLayerStack(ids, mode, goal)
        .then((suggestion) => dispatch({ type: "evaluated", request, suggestion }))
        .catch(() => dispatch({ type: "failed", request }));
    }, EVALUATE_DELAY_MS);
    return () => window.clearTimeout(timer);
    // `key` captures ids, mode and goal.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, dispatch]);
  return { retry: () => { if (ids.length >= 2) { const request = ++counter.current; dispatch({ type: "evaluating", request }); evaluateLayerStack(ids, mode, goal).then((suggestion) => dispatch({ type: "evaluated", request, suggestion })).catch(() => dispatch({ type: "failed", request })); } } };
}
