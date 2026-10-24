"use client";

import { AnimatePresence, motion } from "motion/react";
import { CatalogImage } from "@/components/catalog-image";
import { Badge } from "@/components/ui/badge";
import type { LayeringStackSuggestion } from "@/types/layering";
import styles from "./layering-lab.module.css";

type CanvasItem = {
  fragrance: LayeringStackSuggestion["items"][number]["fragrance"];
  role: "anchor" | "bridge" | "accent";
  suggested_sprays: number | null;
};

const roleLabel = (role: CanvasItem["role"]) =>
  role === "anchor"
    ? "Foundation"
    : role === "bridge"
      ? "Bridge"
      : "Signature";

export function LayeringStudioCanvas({
  items,
  composition,
  pending,
  reducedMotion,
}: {
  items: CanvasItem[];
  composition: LayeringStackSuggestion | null | undefined;
  pending: boolean;
  reducedMotion: boolean | null;
}) {
  return (
    <section
      className={styles.canvas}
      aria-label="Interactive blend canvas"
      aria-busy={pending}
      data-motion={reducedMotion ? "reduced" : "full"}
    >
      <div className={styles.aurora} aria-hidden="true" />
      <div className={styles.orbit} aria-hidden="true" />
      <div className={`${styles.orbit} ${styles.orbitInner}`} aria-hidden="true" />
      <svg className={styles.scentTrails} viewBox="0 0 600 540" aria-hidden="true">
        <path d="M66 330 C165 85 390 470 536 135" />
        <path d="M40 215 C205 455 382 65 560 300" />
        <path d="M100 420 C260 190 420 490 530 210" />
      </svg>
      <motion.div
        className={styles.scoreOrb}
        layout={!reducedMotion}
        animate={pending && !reducedMotion ? { scale: [1, 1.035, 1] } : { scale: 1 }}
        transition={pending && !reducedMotion
          ? { duration: 1.4, repeat: Infinity, ease: "easeInOut" }
          : { type: "spring", stiffness: 160, damping: 24 }}
      >
        <AnimatePresence mode="wait" initial={false}>
          <motion.strong
            key={composition ? Math.round(composition.score * 100) : "empty"}
            className={styles.scoreValue}
            initial={reducedMotion ? false : { opacity: 0, y: 8, filter: "blur(5px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            exit={reducedMotion ? undefined : { opacity: 0, y: -8, filter: "blur(5px)" }}
            transition={{ duration: reducedMotion ? 0 : 0.28, ease: "easeOut" }}
          >
            {composition ? Math.round(composition.score * 100) : "—"}
          </motion.strong>
        </AnimatePresence>
        <span className={styles.scoreVerdict}>{pending ? "Reading blend…" : composition?.verdict ?? "Build your blend"}</span>
      </motion.div>
      <div className={styles.canvasBottles}>
        <AnimatePresence initial={false} mode="popLayout">
          {items.map((item, index) => (
            <motion.article
              layout={!reducedMotion}
              key={item.fragrance.id}
              className={`${styles.canvasBottle} ${styles[`canvasBottle${index + 1}`]}`}
              initial={reducedMotion ? { opacity: 0 } : { opacity: 0, scale: 0.84, y: 28 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={reducedMotion ? { opacity: 0 } : { opacity: 0, scale: 0.84, y: -20 }}
              transition={{ duration: reducedMotion ? 0.01 : 0.34, ease: "easeOut" }}
              data-testid="canvas-bottle"
            >
              <Badge>{roleLabel(item.role)}{item.suggested_sprays ? ` · ${item.suggested_sprays} spray${item.suggested_sprays === 1 ? "" : "s"}` : ""}</Badge>
              <CatalogImage
                id={item.fragrance.id}
                name={item.fragrance.name}
                brand={item.fragrance.brand.name}
                imageUrl={item.fragrance.image_url ?? null}
                className={styles.canvasImage}
              />
              <strong>{item.fragrance.name}</strong>
              <small>{item.fragrance.brand.name}</small>
            </motion.article>
          ))}
        </AnimatePresence>
      </div>
      <ol className={styles.srComposition}>
        {items.map((item, index) => (
          <li key={item.fragrance.id}>
            {index + 1}. {item.fragrance.name}, {roleLabel(item.role)}, {item.suggested_sprays ?? "sprays pending"}
          </li>
        ))}
      </ol>
      <p
        className={styles.scoreAnnouncement}
        role="status"
        aria-label="ScentIQ score update"
        aria-live="polite"
        aria-atomic="true"
      >
        {pending
          ? "ScentIQ is analyzing this blend"
          : composition
            ? `ScentIQ score ${Math.round(composition.score * 100)}. ${composition.verdict}`
            : "Add another fragrance to receive a ScentIQ score"}
      </p>
    </section>
  );
}
