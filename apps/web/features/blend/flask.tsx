import { accordVars, type AccordKey } from "@/lib/accord";

import styles from "./blend.module.css";

export type FlaskLayer = { id: string; accord: AccordKey; sprays: number };

/** Body of the flask, inside which the liquid sits. */
const BODY = "M70 64 V88 C40 100 26 128 26 162 V226 C26 246 40 260 60 260 H140 C160 260 174 246 174 226 V162 C174 128 160 100 130 88 V64 Z";
const FILL_TOP = 104;
const FILL_BOTTOM = 260;

/** Share of the fill height per layer, bottom (first applied) first. */
export function layerHeights(layers: readonly FlaskLayer[]): number[] {
  const total = layers.reduce((sum, layer) => sum + Math.max(layer.sprays, 0), 0);
  if (total <= 0) return layers.map(() => 1 / Math.max(layers.length, 1));
  return layers.map((layer) => Math.max(layer.sprays, 0) / total);
}

/**
 * The glass flask: layers stacked in application order from the bottom, each
 * as tall as its share of the sprays. Decorative; the same information is in
 * text beside it.
 */
export function Flask({ layers, fill = 1 }: { layers: readonly FlaskLayer[]; fill?: number }) {
  const heights = layerHeights(layers);
  const available = (FILL_BOTTOM - FILL_TOP) * Math.max(0, Math.min(1, fill));
  const rects = layers.map((layer, index) => {
    const below = heights.slice(0, index).reduce((sum, share) => sum + share, 0) * available;
    const height = available * heights[index];
    return { layer, y: FILL_BOTTOM - below - height, height };
  });
  return (
    <svg className={styles.flask} viewBox="0 0 200 280" aria-hidden="true" focusable="false">
      <defs>
        <clipPath id="flask-body"><path d={BODY} /></clipPath>
      </defs>
      <g clipPath="url(#flask-body)">
        <rect x="0" y="0" width="200" height="280" style={{ fill: "var(--glass-fill)" }} />
        {rects.map(({ layer, y, height }) => (
          <g key={layer.id} style={accordVars(layer.accord)} data-layer={layer.id}>
            <rect x="0" y={y} width="200" height={height + 1} style={{ fill: "var(--ac)" }} opacity="0.95" />
          </g>
        ))}
        <rect x="44" y="110" width="9" height="130" rx="4.5" fill="#ffffff" opacity="0.14" />
      </g>
      <path d={BODY} fill="none" style={{ stroke: "var(--glass-edge)" }} strokeWidth="2" />
      <rect x="62" y="40" width="76" height="26" rx="8" style={{ fill: "var(--glass-cap)" }} />
    </svg>
  );
}
