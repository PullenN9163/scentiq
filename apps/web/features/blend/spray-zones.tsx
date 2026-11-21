import type { LayeringStackSuggestion } from "@/types/layering";
import { toneFor } from "@/lib/tone";
import styles from "./spray-zones.module.css";

type Zone = NonNullable<LayeringStackSuggestion["items"][number]["zones"]>[number]["zone"];

export const zoneLabels: Record<Zone, string> = {
  chest: "Chest",
  back_of_neck: "Back of neck",
  neck: "Sides of neck",
  wrists: "Wrists",
  inner_elbows: "Inner elbows",
  behind_ears: "Behind ears",
  behind_knees: "Behind knees",
};

// Marker positions on a simple front-view silhouette (viewBox 0 0 120 200).
const anchors: Record<Zone, [number, number]> = {
  chest: [60, 72],
  back_of_neck: [60, 38],
  neck: [48, 40],
  wrists: [28, 118],
  inner_elbows: [34, 92],
  behind_ears: [72, 26],
  behind_knees: [52, 160],
};

export function SprayZones({ stack }: { stack: LayeringStackSuggestion }) {
  const placed = stack.items.flatMap((item) =>
    (item.zones ?? []).map((zone) => ({
      id: item.fragrance.id,
      name: item.fragrance.name,
      color: toneFor(item.fragrance.id),
      ...zone,
    })),
  );
  return (
    <div className={styles.wrap}>
      <svg viewBox="0 0 120 200" className={styles.body} aria-hidden="true" focusable="false">
        <circle cx="60" cy="20" r="14" />
        <path d="M44 38h32l14 12 6 50-10 4-6-36v50l4 54h-12l-8-52-8 52H46l4-54V68l-6 36-10-4 6-50z" />
        {placed.map((mark, index) => {
          const [cx, cy] = anchors[mark.zone];
          return (
            <circle
              key={`${mark.id}-${mark.zone}`}
              cx={cx + (index % 2) * 4}
              cy={cy}
              r={4 + mark.sprays}
              fill={mark.color}
              stroke="#fff"
              strokeWidth="1.5"
              opacity="0.9"
            />
          );
        })}
      </svg>
      <ol className={styles.list} aria-label="Where to spray">
        {stack.items.map((item) => (
          <li key={item.fragrance.id}>
            <strong>{item.fragrance.name}</strong>
            <span>
              {(item.zones ?? [])
                .map((zone) => `${zoneLabels[zone.zone]} ×${zone.sprays}`)
                .join(" · ") || `${item.suggested_sprays} sprays`}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
