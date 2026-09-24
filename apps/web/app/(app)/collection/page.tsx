import { Suspense } from "react";

import { LoadingState } from "@/components/shared/states";
import { CollectionBoundary } from "@/features/collection/collection-boundary";

export default function CollectionPage() {
  return (
    <Suspense fallback={<LoadingState rows={4} label="Loading your collection" />}>
      <CollectionBoundary />
    </Suspense>
  );
}
