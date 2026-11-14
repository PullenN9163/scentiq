"use client";

import { motion } from "motion/react";

import { accordVars, type AccordKey } from "@/lib/accord";
import { motionTokens } from "@/lib/motion";

import styles from "./blend.module.css";

export type FlaskLayer = { id: string; accord: AccordKey; sprays: number };

/** Body of the flask, inside which the liquid sits. */
const BODY = "M70 64 V88 C40 100 26 128 26 162 V226 C26 246 40 260 60 260 H140 C160 260 174 246 174 226 V162 C174 128 160 100 130 88 V64 Z";
const FILL_TOP = 104;
const FILL_BOTTOM = 260;
/** One wave period is 100 units, so the drift loops seamlessly over 100 units. */
const WAVE = `M-100 0 q25 -9 50 0${" t50 0".repeat(7)} V300 H-100 Z`;
/** Loop length per layer, so the layers drift at different speeds (seconds). */
const DRIFT_SECONDS = [6.5, 8, 7.2, 9];
const BUBBLES = [
  { cx: 84, cy: 236, delay: "0s" },
  { cx: 112, cy: 226, delay: "-3s" },
  { cx: 136, cy: 244, delay: "-5.5s" },
];

/** Share of the fill height per layer, bottom (first applied) first. */
export function layerHeights(layers: readonly FlaskLayer[]): number[] {
  const total = layers.reduce((sum, layer) => sum + Math.max(layer.sprays, 0), 0);
  if (total <= 0) return layers.map(() => 1 / Math.max(layers.length, 1));
  return layers.map((layer) => Math.max(layer.sprays, 0) / total);
}

/**
 * Where each layer's surface sits (its top edge), bottom layer first. A layer
 * is painted from its top edge down to the foot of the flask, so the layers
 * above overlap the ones below only where they should.
 */
export function layerTops(layers: readonly FlaskLayer[], fill: number): number[] {
  const available = (FILL_BOTTOM - FILL_TOP) * Math.max(0, Math.min(1, fill));
  const shares = layerHeights(layers);
  let below = 0;
  return shares.map((share) => {
    below += share;
    return FILL_BOTTOM - below * available;
  });
}

/**
 * The glass flask: layers stacked in application order from the bottom, each
 * as tall as its share of the sprays. Layer heights are Motion springs; the
 * waves and bubbles drift in CSS. Decorative; the same information is in text
 * beside it.
 */
export function Flask({ layers, fill = 1 }: { layers: readonly FlaskLayer[]; fill?: number }) {
  const tops = layerTops(layers, fill);
  // The highest layer is painted first, so each lower layer covers its foot.
  const paint = layers.map((layer, index) => ({ layer, index, top: tops[index] })).reverse();
  return (
    <svg className={styles.flask} viewBox="0 0 200 280" aria-hidden="true" focusable="false">
      <defs>
        <clipPath id="flask-body"><path d={BODY} /></clipPath>
      </defs>
      <g clipPath="url(#flask-body)">
        <rect x="0" y="0" width="200" height="280" style={{ fill: "var(--glass-fill)" }} />
        {paint.map(({ layer, index, top }) => (
          <motion.g
            key={layer.id}
            data-layer={layer.id}
            style={accordVars(layer.accord)}
            initial={{ y: FILL_BOTTOM }}
            animate={{ y: top }}
            transition={motionTokens.springLively}
          >
            <g className={styles.wave} style={{ animationDuration: `${DRIFT_SECONDS[index % DRIFT_SECONDS.length]}s` }}>
              <path d={WAVE} style={{ fill: "var(--ac)" }} opacity="0.95" />
            </g>
          </motion.g>
        ))}
        {BUBBLES.map((bubble) => (
          <circle key={bubble.cx} className={styles.bubble} cx={bubble.cx} cy={bubble.cy} r="2.6" style={{ animationDelay: bubble.delay, fill: "#ffffff" }} />
        ))}
        <rect x="44" y="110" width="9" height="130" rx="4.5" fill="#ffffff" opacity="0.14" />
      </g>
      <path d={BODY} fill="none" style={{ stroke: "var(--glass-edge)" }} strokeWidth="2" />
      <rect x="62" y="40" width="76" height="26" rx="8" style={{ fill: "var(--glass-cap)" }} />
    </svg>
  );
}
