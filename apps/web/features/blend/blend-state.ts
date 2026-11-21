import type { LayeringGoal, LayeringStackSuggestion, StackMode } from "@/types/layering";

export const MAX_BOTTLES = 3;

export type BlendSnapshot = { ids: string[]; mode: StackMode; goal: LayeringGoal | null };

export type BlendState = BlendSnapshot & {
  /** The latest evaluation for the current ids, mode and goal. */
  suggestion: LayeringStackSuggestion | null;
  status: "idle" | "evaluating" | "error";
  /** Set when the flask holds a saved blend unchanged. */
  savedId: string | null;
  /** Single-step undo. */
  history: BlendSnapshot[];
  /** Evaluation request counter, for ignoring stale responses. */
  request: number;
  /** The id most recently added, for the add sequence and announcements. */
  lastAdded: string | null;
};

export type BlendAction =
  | { type: "toggle"; id: string }
  | { type: "add"; id: string }
  | { type: "remove"; id: string }
  | { type: "mode"; mode: StackMode }
  | { type: "goal"; goal: LayeringGoal | null }
  | { type: "load"; ids: string[]; mode?: StackMode; goal?: LayeringGoal | null; savedId?: string | null; suggestion?: LayeringStackSuggestion | null }
  | { type: "evaluating"; request: number }
  | { type: "evaluated"; request: number; suggestion: LayeringStackSuggestion }
  | { type: "failed"; request: number }
  | { type: "saved"; savedId: string }
  | { type: "undo" };

export function initialBlend(snapshot: Partial<BlendSnapshot> & { savedId?: string | null; suggestion?: LayeringStackSuggestion | null } = {}): BlendState {
  return {
    ids: (snapshot.ids ?? []).slice(0, MAX_BOTTLES),
    mode: snapshot.mode ?? "balanced",
    goal: snapshot.goal ?? null,
    suggestion: snapshot.suggestion ?? null,
    status: "idle",
    savedId: snapshot.savedId ?? null,
    history: [],
    request: 0,
    lastAdded: null,
  };
}

function snapshot(state: BlendState): BlendSnapshot {
  return { ids: state.ids, mode: state.mode, goal: state.goal };
}

/** A change to what is in the flask: remember one step for undo, forget the saved match. */
function change(state: BlendState, next: Partial<BlendSnapshot>, lastAdded: string | null = null): BlendState {
  const ids = next.ids ?? state.ids;
  return {
    ...state,
    ...next,
    ids,
    history: [snapshot(state)],
    savedId: null,
    lastAdded,
    suggestion: ids.length < 2 ? null : state.suggestion,
    status: ids.length < 2 ? "idle" : state.status,
  };
}

export function blendReducer(state: BlendState, action: BlendAction): BlendState {
  switch (action.type) {
    case "add": {
      if (state.ids.includes(action.id)) return state;
      // A fourth bottle replaces the oldest.
      const ids = [...state.ids, action.id].slice(-MAX_BOTTLES);
      return change(state, { ids }, action.id);
    }
    case "remove":
      if (!state.ids.includes(action.id)) return state;
      return change(state, { ids: state.ids.filter((id) => id !== action.id) });
    case "toggle":
      return blendReducer(state, state.ids.includes(action.id) ? { type: "remove", id: action.id } : { type: "add", id: action.id });
    case "mode":
      return action.mode === state.mode ? state : change(state, { mode: action.mode });
    case "goal":
      // Tapping the selected tilt clears it.
      return change(state, { goal: action.goal === state.goal ? null : action.goal });
    case "load":
      return {
        ...initialBlend({ ids: action.ids, mode: action.mode ?? state.mode, goal: action.goal === undefined ? state.goal : action.goal, savedId: action.savedId ?? null, suggestion: action.suggestion ?? null }),
        history: [snapshot(state)],
        request: state.request,
        lastAdded: action.ids[action.ids.length - 1] ?? null,
      };
    case "evaluating":
      return { ...state, status: "evaluating", request: action.request };
    case "evaluated":
      if (action.request !== state.request) return state;
      return { ...state, status: "idle", suggestion: action.suggestion };
    case "failed":
      if (action.request !== state.request) return state;
      return { ...state, status: "error" };
    case "saved":
      return { ...state, savedId: action.savedId };
    case "undo": {
      const previous = state.history[0];
      if (!previous) return state;
      return { ...state, ...previous, history: [], savedId: null, lastAdded: null, suggestion: previous.ids.length < 2 ? null : state.suggestion };
    }
    default:
      return state;
  }
}

/** Same bottles, mode and goal as a saved blend (order does not matter). */
export function sameBlend(a: BlendSnapshot, b: BlendSnapshot): boolean {
  return a.mode === b.mode && (a.goal ?? null) === (b.goal ?? null) && a.ids.length === b.ids.length && [...a.ids].sort().join() === [...b.ids].sort().join();
}

/** Whether the current suggestion describes exactly the bottles in the flask. */
export function suggestionMatches(state: Pick<BlendState, "ids" | "suggestion">): boolean {
  const suggestion = state.suggestion;
  if (!suggestion) return false;
  const ids = suggestion.items.map((item) => item.fragrance.id);
  return ids.length === state.ids.length && ids.every((id) => state.ids.includes(id));
}

/** What the studio opens with: the query, a saved blend, or an empty flask. */
export type BlendStart = BlendSnapshot & { savedId?: string | null; suggestion?: LayeringStackSuggestion | null };
