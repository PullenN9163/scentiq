import type { LayeringGoal, StackMode } from "@/types/layering";

export const PRIMARY_GOALS: LayeringGoal[] = ["fresher", "warmer", "sweeter", "darker", "softer", "more_projection"];
export const MORE_GOALS: LayeringGoal[] = ["cleaner", "more_intimate", "daytime", "evening", "spring", "summer", "fall", "winter"];
export const GOAL_LABELS: Record<LayeringGoal, string> = {
  fresher: "Fresher", warmer: "Warmer", sweeter: "Sweeter", darker: "Darker", softer: "Softer", more_projection: "More projection",
  cleaner: "Cleaner", more_intimate: "More intimate", daytime: "Daytime", evening: "Evening", spring: "Spring", summer: "Summer", fall: "Fall", winter: "Winter",
};
export const MODES: { value: StackMode; label: string }[] = [
  { value: "safe", label: "Safe" },
  { value: "balanced", label: "Balanced" },
  { value: "contrast", label: "Contrast" },
  { value: "experimental", label: "Experimental" },
];
const MODE_VALUES = MODES.map((mode) => mode.value);
const GOAL_VALUES = [...PRIMARY_GOALS, ...MORE_GOALS];

export function toMode(value: string | null | undefined): StackMode {
  return MODE_VALUES.includes(value as StackMode) ? (value as StackMode) : "balanced";
}

export function toGoal(value: string | null | undefined): LayeringGoal | null {
  return GOAL_VALUES.includes(value as LayeringGoal) ? (value as LayeringGoal) : null;
}

/** Score 0 to 1 as a whole number out of 100. */
export function scoreOf(score: number): number {
  return Math.round(score * 100);
}
