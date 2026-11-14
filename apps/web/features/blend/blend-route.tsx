import { AtelierError, AtelierUnavailable } from "@/components/atelier/states";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/server/api-client";
import { evaluateLayerStack, getLayeringIntelligence } from "@/lib/server/layering-actions";
import { getCollection } from "@/lib/server/queries";
import type { CollectionItem } from "@/types/api";
import type { LayeringGoal, LayeringIntelligencePage } from "@/types/layering";

import { BlendStudio } from "./blend-studio";
import { blendStartFromQuery, shelfOrder, type BlendQuery } from "./blend-start";
import type { BlendStart } from "./blend-state";
import styles from "./blend.module.css";

/** Supplementary read: a failure leaves the saved blends empty rather than failing the room. */
async function optional(read: Promise<LayeringIntelligencePage>): Promise<LayeringIntelligencePage | null> {
  try {
    return await read;
  } catch (error) {
    if (error instanceof ApiError && error.kind === "unauthorized") throw error;
    return null;
  }
}

/** The studio's server half: the owned shelf, the query's starting blend, and a first reading when the query asks for one. */
export async function BlendRoute({ query }: { query: BlendQuery }) {
  let owned: CollectionItem[];
  let supportedGoals: LayeringGoal[] | undefined;
  let start: BlendStart;
  try {
    const [collection, intelligence] = await Promise.all([
      getCollection(),
      optional(getLayeringIntelligence({ mode: "balanced" })),
    ]);
    owned = shelfOrder(collection.filter((item) => item.status === "owned"));
    supportedGoals = intelligence?.supported_goals;
    const load = blendStartFromQuery(query, owned, intelligence?.saved ?? []);
    start = load.start;
    if (load.evaluate) {
      // A failed first reading is left to the studio, which shows it with a retry.
      const suggestion = await evaluateLayerStack(start.ids, start.mode, start.goal).catch(() => null);
      start = { ...start, suggestion };
    }
  } catch (error) {
    if (error instanceof ApiError && error.kind === "unavailable") return <AtelierUnavailable />;
    if (error instanceof ApiError) return <div className="at-page"><AtelierError title="The blend room did not load" message={error.message} /></div>;
    throw error;
  }
  return <BlendStudio owned={owned} supportedGoals={supportedGoals} start={start} />;
}

/** Plate skeletons while the shelf loads. */
export function BlendSkeleton() {
  return (
    <div className={styles.room} data-theme="dark" aria-busy="true" aria-label="Loading the blend room">
      <header className={styles.bar} />
      <div className={styles.stage} />
      <div className={styles.shelf}>
        <ul className={styles.rail}>
          {Array.from({ length: 6 }, (_, index) => <li key={index}><Skeleton className={styles.skeletonPlate} /></li>)}
        </ul>
      </div>
    </div>
  );
}
