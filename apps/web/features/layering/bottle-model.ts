import { toneFor } from "@/lib/tone";
import type { LayeringStackSuggestion } from "@/types/layering";

export type BottleSegment = {
  id: string;
  name: string;
  color: string;
  sprays: number;
  /** Share of the liquid column, 0-1. Shares always sum to 1. */
  share: number;
};

/** Liquid bands, bottom to top: the anchor (first applied) sits at the base. */
export function bottleSegments(
  stack: Pick<LayeringStackSuggestion, "items">,
): BottleSegment[] {
  const total = stack.items.reduce((sum, item) => sum + item.suggested_sprays, 0) || 1;
  return stack.items.map((item) => ({
    id: item.fragrance.id,
    name: item.fragrance.name,
    color: toneFor(item.fragrance.id),
    sprays: item.suggested_sprays,
    share: item.suggested_sprays / total,
  }));
}

export function bottleDescription(
  stack: Pick<LayeringStackSuggestion, "items" | "score_percent">,
): string {
  const parts = bottleSegments(stack).map(
    (segment) => `${segment.name} ${Math.round(segment.share * 100)}%`,
  );
  return `Cologne bottle holding a ${stack.score_percent}% match blend: ${parts.join(", ")}`;
}

/** True when this browser can create a WebGL context (false in SSR and some test runners). */
export function webglAvailable(): boolean {
  if (typeof document === "undefined") return false;
  try {
    const canvas = document.createElement("canvas");
    return Boolean(
      canvas.getContext("webgl2") ?? canvas.getContext("webgl"),
    );
  } catch {
    return false;
  }
}

/** Start of each band as a fraction of the liquid column, measured from the bottom. */
export function bandStarts(segments: Pick<BottleSegment, "share">[]): number[] {
  return segments.map((_, index) =>
    segments.slice(0, index).reduce((sum, item) => sum + item.share, 0),
  );
}
