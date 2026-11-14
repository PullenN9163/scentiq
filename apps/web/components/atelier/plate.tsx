"use client";

import Image from "next/image";
import { motion } from "motion/react";
import { useState, type CSSProperties, type ReactNode } from "react";

import { useRemoteImagesEnabled } from "@/components/catalog-image";
import { accordVars, type AccordKey } from "@/lib/accord";
import { cn } from "@/lib/utils";

import styles from "./plate.module.css";

export type PlateFragrance = {
  id: string;
  name: string;
  brand: string;
  imageUrl: string | null;
};

/** Shape a catalog fragrance for a plate. */
export function plateFragrance(fragrance: {
  id: string;
  name: string;
  brand: { name: string };
  image_url?: string | null;
}): PlateFragrance {
  return { id: fragrance.id, name: fragrance.name, brand: fragrance.brand.name, imageUrl: fragrance.image_url ?? null };
}

/**
 * The tinted plate a bottle sits on. The photo is blended with multiply so its
 * white background takes the accord color, in both themes. With no usable
 * photo the plate shows the house name; there is no drawn placeholder bottle.
 */
export function Plate({
  fragrance,
  accord,
  className,
  sizes,
  priority = false,
  decorative = false,
  layoutId,
  style,
  compact = false,
  children,
}: {
  fragrance: PlateFragrance;
  accord: AccordKey;
  className?: string;
  sizes?: string;
  priority?: boolean;
  /** True when the name is printed beside the plate, so the photo needs no alt text. */
  decorative?: boolean;
  /** Shared-element id, so the plate can travel between views. */
  layoutId?: string;
  style?: CSSProperties;
  /** Small plates (rows, strips) leave out the house name when there is no photo. */
  compact?: boolean;
  children?: ReactNode;
}) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const remoteEnabled = useRemoteImagesEnabled();
  const imageUrl = fragrance.imageUrl;
  const privateImage = imageUrl?.startsWith("/api/fragrances/") ?? false;
  const showPhoto = Boolean(imageUrl) && (remoteEnabled || privateImage) && failedUrl !== imageUrl;
  return (
    <motion.div
      layoutId={layoutId}
      className={cn(styles.plate, className)}
      data-accord={accord}
      data-photo={showPhoto ? "true" : "false"}
      style={{ ...accordVars(accord), ...style }}
    >
      {showPhoto && imageUrl ? (
        <Image
          className={styles.photo}
          src={imageUrl}
          alt={decorative ? "" : `${fragrance.name} by ${fragrance.brand}`}
          width={375}
          height={500}
          sizes={sizes ?? "(max-width: 700px) 45vw, (max-width: 1100px) 24vw, 240px"}
          priority={priority}
          unoptimized={privateImage}
          onError={() => setFailedUrl(imageUrl)}
        />
      ) : compact ? (
        <span className="sr-only" data-testid="plate-fallback">{decorative ? "" : `${fragrance.name} by ${fragrance.brand}`}</span>
      ) : (
        <span className={cn(styles.house, "at-overline")} data-testid="plate-fallback">
          {fragrance.brand}
          {!decorative && <span className="sr-only">{` ${fragrance.name}`}</span>}
        </span>
      )}
      {children}
    </motion.div>
  );
}
