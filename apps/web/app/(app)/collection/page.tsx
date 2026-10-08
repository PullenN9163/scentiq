import { Suspense } from "react";

import { LoadingState } from "@/components/shared/states";
import { CollectionBoundary } from "@/features/collection/collection-boundary";
import { Skeleton } from "@/components/ui/skeleton";

export default function CollectionPage() {
  return (
    <Suspense fallback={<div className="page"><LoadingState rows={1} label="Loading your collection" /><div className="fragrance-grid">{Array.from({ length: 6 }, (_, index) => <Skeleton key={index} className="collection-card-skeleton" />)}</div></div>}>
      <CollectionBoundary />
    </Suspense>
  );
}
