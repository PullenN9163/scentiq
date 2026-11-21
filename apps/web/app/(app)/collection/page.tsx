import { Suspense } from "react";

import { LoadingState } from "@/components/shared/states";
import { CollectionBoundary } from "@/features/collection/collection-boundary";
import { CollectionSkeleton } from "@/features/collection-atelier/collection-atelier";
import { CollectionAtelierBoundary } from "@/features/collection-atelier/collection-atelier-boundary";
import { Skeleton } from "@/components/ui/skeleton";
import { isAtelierEnabled } from "@/lib/atelier-flag";

export default async function CollectionPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  if (isAtelierEnabled()) {
    const { segment } = await searchParams;
    const initial = segment === "wishlist" || segment === "blends" ? segment : "shelf";
    return (
      <Suspense fallback={<CollectionSkeleton />}>
        <CollectionAtelierBoundary segment={initial} />
      </Suspense>
    );
  }
  return (
    <Suspense fallback={<div className="page"><LoadingState rows={1} label="Loading your collection" /><div className="fragrance-grid">{Array.from({ length: 6 }, (_, index) => <Skeleton key={index} className="collection-card-skeleton" />)}</div></div>}>
      <CollectionBoundary />
    </Suspense>
  );
}
