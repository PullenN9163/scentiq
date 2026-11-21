import { accordVars, type AccordKey } from "@/lib/accord";
import { cn } from "@/lib/utils";

import styles from "./vial.module.css";

export type VialLayer = { id: string; accord: AccordKey; sprays: number };

/**
 * A blend as a rounded vial of horizontal stripes. Stripe heights follow the
 * spray split; colors are each fragrance's chart color. Layers are listed
 * bottom (first applied) to top. Decorative: the names travel beside it.
 */
export function Vial({ layers, size = "md", className }: { layers: readonly VialLayer[]; size?: "sm" | "md" | "lg"; className?: string }) {
  const total = layers.reduce((sum, layer) => sum + Math.max(layer.sprays, 0), 0) || layers.length || 1;
  return (
    <span className={cn(styles.vial, styles[size], className)} aria-hidden="true">
      <span className={styles.liquid}>
        {[...layers].reverse().map((layer) => (
          <span key={layer.id} className={styles.layer} style={{ ...accordVars(layer.accord), flexGrow: Math.max(layer.sprays, 0) / total || 1 / layers.length }} />
        ))}
      </span>
    </span>
  );
}
