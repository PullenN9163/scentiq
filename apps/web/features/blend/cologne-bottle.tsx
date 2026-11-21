"use client";

import dynamic from "next/dynamic";
import { Component, useRef, useSyncExternalStore, type ReactNode } from "react";

import { effectsReduced, resolveColor } from "@/components/atelier/mist";
import type { AccordKey } from "@/lib/accord";

import { webglAvailable, type BottleLayer } from "./bottle-model";
import { Flask, type FlaskLayer } from "./flask";
import styles from "./blend.module.css";

const Scene = dynamic(() => import("./cologne-scene"), { ssr: false });

class SceneBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

/**
 * The blend as a 3D cologne bottle with a pump atomizer: glass shell, gold collar, liquid bands
 * sized by each scent's share of the sprays. Without WebGL (or if the scene fails) the SVG flask
 * is shown instead. Decorative; the same information is in text beside it.
 */
export function CologneBottle({
  layers,
  fill,
  title,
  percent,
  sprayKey,
}: {
  layers: readonly FlaskLayer[];
  fill: number;
  title: string;
  percent: number | null;
  /** Changes whenever a scent is added, which fires the atomizer. */
  sprayKey: string;
}) {
  const wrapper = useRef<HTMLDivElement>(null);
  // Client-only capability check; the server and first paint use the flat flask.
  const canRender = useSyncExternalStore(() => () => {}, webglAvailable, () => false);
  const flask = <Flask layers={layers} fill={fill} />;
  if (!canRender) return flask;
  const colorOf = (accord: AccordKey) =>
    resolveColor(wrapper.current ?? document.documentElement, `--chart-${accord === "neutral" ? "musk" : accord}`);
  return (
    <div ref={wrapper} className={styles.cologne} aria-hidden="true">
      <SceneBoundary fallback={flask}>
        <Scene
          layers={layers as readonly BottleLayer[]}
          colorOf={colorOf}
          fill={fill}
          title={title}
          percent={percent}
          sprayKey={sprayKey}
          reducedMotion={effectsReduced()}
        />
      </SceneBoundary>
    </div>
  );
}
