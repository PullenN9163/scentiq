"use client";

import dynamic from "next/dynamic";
import { Component, useState, useSyncExternalStore, type ReactNode } from "react";
import { useReducedMotion } from "motion/react";
import { SprayCan } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  bandStarts,
  bottleDescription,
  bottleSegments,
  webglAvailable,
  type BottleSegment,
} from "./bottle-model";
import type { LayeringStackSuggestion } from "@/types/layering";
import styles from "./blend-bottle.module.css";

const Scene = dynamic(() => import("./blend-bottle-scene"), {
  ssr: false,
  loading: () => <div className={styles.loading}>Preparing bottle…</div>,
});

class SceneBoundary extends Component<
  { fallback: ReactNode; children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

/** A flat bottle used when WebGL is unavailable. Same proportions and colours as the 3D one. */
export function BottleFallback({ segments }: { segments: BottleSegment[] }) {
  const top = 70;
  const bottom = 214;
  const column = bottom - top;
  const starts = bandStarts(segments);
  return (
    <svg viewBox="0 0 160 260" className={styles.fallback} aria-hidden="true" focusable="false">
      <rect x="62" y="6" width="36" height="18" rx="4" fill="#c9a45c" />
      <rect x="72" y="22" width="16" height="14" rx="2" fill="#b08a43" />
      <rect x="56" y="36" width="48" height="16" rx="3" fill="#c9a45c" />
      <rect x="64" y="50" width="32" height="12" fill="#e8f1f4" opacity="0.7" />
      <rect x="22" y="62" width="116" height="164" rx="16" fill="#eaf3f6" opacity="0.55" stroke="#b9ccd3" />
      {segments.map((segment, index) => {
        const height = column * segment.share;
        const y = bottom - column * starts[index] - height;
        return (
          <rect key={segment.id} x="30" y={y} width="100" height={height} fill={segment.color} opacity="0.9" />
        );
      })}
      <rect x="22" y="62" width="116" height="164" rx="16" fill="none" stroke="#9fb6bf" strokeWidth="2" />
    </svg>
  );
}

export function BlendBottle({ stack }: { stack: LayeringStackSuggestion }) {
  const reduced = useReducedMotion() ?? false;
  const [trigger, setTrigger] = useState(0);
  // Client-only capability check; the server and first paint use the flat bottle.
  const canRender = useSyncExternalStore(
    () => () => {},
    webglAvailable,
    () => false,
  );
  const segments = bottleSegments(stack);
  const title = stack.items.map((item) => item.fragrance.name).join(" + ");
  const fallback = <BottleFallback segments={segments} />;
  return (
    <figure className={styles.figure}>
      <div className={styles.stage} role="img" aria-label={bottleDescription(stack)}>
        {canRender ? (
          <SceneBoundary fallback={fallback}>
            <Scene
              segments={segments}
              title={title}
              percent={stack.score_percent}
              trigger={trigger}
              reducedMotion={reduced}
            />
          </SceneBoundary>
        ) : (
          fallback
        )}
      </div>
      <figcaption className={styles.caption}>
        <Button variant="secondary" onClick={() => setTrigger((value) => value + 1)}>
          <SprayCan size={16} aria-hidden="true" /> Test spray
        </Button>
        <span className="data-note">
          Liquid bands show each scent&apos;s share of the sprays.
        </span>
      </figcaption>
    </figure>
  );
}
