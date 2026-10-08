import { LayeringLab } from "@/features/layering/layering-lab";
import { getCollection } from "@/lib/server/queries";
import {
  evaluateLayerStack,
  getLayeringIntelligence,
} from "@/lib/server/layering-actions";
import type { LayeringGoal, StackMode } from "@/types/layering";

export default async function LayeringPage({
  searchParams,
}: {
  searchParams: Promise<{
    a?: string;
    stack?: string;
    mode?: string;
    goal?: string;
  }>;
}) {
  const parameters = await searchParams;
  const collection = await getCollection();
  const owned = collection
    .filter((item) => item.status === "owned")
    .map((item) => item.fragrance);
  const modes = ["safe", "balanced", "contrast", "experimental"];
  const goals = [
    "fresher",
    "warmer",
    "sweeter",
    "darker",
    "cleaner",
    "softer",
    "more_projection",
    "more_intimate",
    "daytime",
    "evening",
    "spring",
    "summer",
    "fall",
    "winter",
  ];
  const mode = modes.includes(parameters.mode ?? "")
    ? (parameters.mode as StackMode)
    : "balanced";
  const goal = goals.includes(parameters.goal ?? "")
    ? (parameters.goal as LayeringGoal)
    : null;
  const ids = parameters.stack?.split(",") ?? [];
  const validStack =
    ids.length >= 2 &&
    ids.length <= 3 &&
    new Set(ids).size === ids.length &&
    ids.every((id) => owned.some((item) => item.id === id));
  const anchor = validStack
    ? ids[0]
    : (owned.find((item) => item.id === parameters.a)?.id ?? owned[0]?.id);
  const [intelligence, stack] = await Promise.all([
    getLayeringIntelligence({ anchorId: anchor, mode, goal }),
    validStack
      ? evaluateLayerStack(ids, mode, goal)
      : Promise.resolve(undefined),
  ]);
  return (
    <LayeringLab
      initialA={anchor}
      owned={owned}
      initialIntelligence={intelligence}
      initialStack={stack}
    />
  );
}
