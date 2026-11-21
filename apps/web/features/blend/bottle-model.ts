import type { AccordKey } from "@/lib/accord";
import type { LayeringStackSuggestion } from "@/types/layering";

export type BottleLayer = { id: string; accord: AccordKey; sprays: number };

export type BottleSegment = {
  id: string;
  color: string;
  sprays: number;
  /** Share of the liquid column, 0-1. Shares always sum to 1. */
  share: number;
};

/** Liquid bands, bottom (first applied) to top, sized by each scent's share of the sprays. */
export function bottleSegments(
  layers: readonly BottleLayer[],
  colorOf: (accord: AccordKey) => string,
): BottleSegment[] {
  const total = layers.reduce((sum, layer) => sum + Math.max(layer.sprays, 0), 0);
  return layers.map((layer) => ({
    id: layer.id,
    color: colorOf(layer.accord),
    sprays: layer.sprays,
    share: total > 0 ? Math.max(layer.sprays, 0) / total : 1 / Math.max(layers.length, 1),
  }));
}

/** Start of each band as a fraction of the liquid column, measured from the bottom. */
export function bandStarts(segments: Pick<BottleSegment, "share">[]): number[] {
  return segments.map((_, index) =>
    segments.slice(0, index).reduce((sum, item) => sum + item.share, 0),
  );
}

export function bottleDescription(
  stack: Pick<LayeringStackSuggestion, "items" | "score_percent"> | null,
  layers: readonly BottleLayer[],
): string {
  const names = stack?.items.map((item) => item.fragrance.name) ?? [];
  const total = layers.reduce((sum, layer) => sum + layer.sprays, 0) || 1;
  const parts = layers.map(
    (layer, index) => `${names[index] ?? "Scent"} ${Math.round((layer.sprays / total) * 100)}%`,
  );
  return stack
    ? `Cologne bottle holding a ${stack.score_percent}% match blend: ${parts.join(", ")}`
    : "Cologne bottle";
}

/** True when this browser can create a WebGL context (false in SSR and in jsdom). */
export function webglAvailable(): boolean {
  if (typeof document === "undefined") return false;
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") ?? canvas.getContext("webgl"));
  } catch {
    return false;
  }
}
