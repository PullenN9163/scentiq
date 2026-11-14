import { notFound } from "next/navigation";
import { Suspense } from "react";

import { AtelierError, AtelierUnavailable } from "@/components/atelier/states";
import { ErrorState, LoadingState, UnavailableState } from "@/components/shared/states";
import { FragranceDetailView } from "@/features/collection/fragrance-detail-view";
import { ApiError } from "@/lib/server/api-client";
import { getLayeringIntelligence } from "@/lib/server/layering-actions";
import { getFragrancePage } from "@/lib/server/queries";
import type { FragrancePageData } from "@/types/api";
import type { LayeringStackSuggestion } from "@/types/layering";

import { FragranceContent, FragranceSkeleton } from "./fragrance-content";
import { FragranceSheetFrame } from "./fragrance-sheet-frame";
import { InterceptGuard } from "./intercept-guard";
import { LayersWellWith, LayersWellWithSkeleton } from "./layers-well-with";
import { RetryButton } from "./retry-button";

export type FragranceQuery = Record<string, string | string[] | undefined>;

/** The back link, keeping the existing ?from=discover&q= behavior. */
export function backFor(query: FragranceQuery): { href: string; label: string } {
  const fromDiscover = query.from === "discover";
  const discoverParameters = new URLSearchParams();
  const discoverQuery = typeof query.q === "string" ? query.q.trim() : "";
  if (discoverQuery) discoverParameters.set("q", discoverQuery);
  return fromDiscover
    ? { href: `/discover${discoverParameters.size ? `?${discoverParameters.toString()}` : ""}`, label: "Back to Discover" }
    : { href: "/collection", label: "Back to collection" };
}

async function load(fragranceId: string): Promise<FragrancePageData | { failure: "unavailable" | "error"; message: string }> {
  try {
    return await getFragrancePage(fragranceId);
  } catch (error) {
    if (error instanceof ApiError && error.kind === "not_found") notFound();
    if (error instanceof ApiError && error.kind === "unavailable") return { failure: "unavailable", message: error.message };
    if (error instanceof ApiError) return { failure: "error", message: error.message };
    throw error;
  }
}

/** The existing detail page, unchanged, for the flag-off path. */
async function LegacyDetail({ fragranceId, back }: { fragranceId: string; back: { href: string; label: string } }) {
  const data = await load(fragranceId);
  if ("failure" in data) return data.failure === "unavailable" ? <UnavailableState /> : <ErrorState message={data.message} />;
  return <FragranceDetailView fragrance={data.fragrance} ownedItem={data.collection_item} wears={data.recent_wears} backHref={back.href} backLabel={back.label} />;
}

async function LayersFor({ anchorId }: { anchorId: string }) {
  let suggestions: LayeringStackSuggestion[];
  try {
    suggestions = (await getLayeringIntelligence({ anchorId })).suggestions;
  } catch (error) {
    if (error instanceof ApiError && error.kind === "unauthorized") throw error;
    return null;
  }
  return <LayersWellWith anchorId={anchorId} suggestions={suggestions} />;
}

async function AtelierDetail({ fragranceId, variant, back }: { fragranceId: string; variant: "page" | "sheet"; back?: { href: string; label: string } }) {
  const data = await load(fragranceId);
  if ("failure" in data) {
    if (data.failure === "unavailable" && variant === "page") return <AtelierUnavailable retry={<RetryButton />} />;
    return <AtelierError title="This fragrance did not load" message={data.message} retry={<RetryButton />} />;
  }
  return (
    <FragranceContent
      data={data}
      variant={variant}
      back={back}
      layersWell={<Suspense fallback={<LayersWellWithSkeleton />}><LayersFor anchorId={data.fragrance.id} /></Suspense>}
    />
  );
}

/** Full page for /collection/[id] on a direct load or refresh. */
export function FragrancePageRoute({ fragranceId, query, atelier }: { fragranceId: string; query: FragranceQuery; atelier: boolean }) {
  const back = backFor(query);
  if (!atelier) {
    return (
      <Suspense fallback={<LoadingState rows={4} label="Loading fragrance" />}>
        <LegacyDetail fragranceId={fragranceId} back={back} />
      </Suspense>
    );
  }
  return (
    <div className="at-page">
      <Suspense fallback={<FragranceSkeleton />}>
        <AtelierDetail fragranceId={fragranceId} variant="page" back={{ href: back.href, label: back.label.replace("Back to collection", "Collection").replace("Back to Discover", "Discover") }} />
      </Suspense>
    </div>
  );
}

/**
 * The intercepted route for a soft navigation to /collection/[id]. With the
 * flag on it is the fragrance sheet. With the flag off it renders the existing
 * detail page in place of the page behind it, so the old interface is
 * unchanged (see `legacy-intercepted-page` in globals.css).
 */
export function FragranceSheetRoute({ fragranceId, query, atelier }: { fragranceId: string; query: FragranceQuery; atelier: boolean }) {
  if (!atelier) {
    return <InterceptGuard id={fragranceId}><div className="legacy-intercepted-page">{FragrancePageRoute({ fragranceId, query, atelier })}</div></InterceptGuard>;
  }
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) if (typeof value === "string") search.set(key, value);
  const fullHref = `/collection/${fragranceId}${search.size ? `?${search.toString()}` : ""}`;
  return (
    <InterceptGuard id={fragranceId}>
    <FragranceSheetFrame id={fragranceId} title="Fragrance" fullHref={fullHref}>
      <Suspense fallback={<FragranceSkeleton />}>
        <AtelierDetail fragranceId={fragranceId} variant="sheet" />
      </Suspense>
    </FragranceSheetFrame>
    </InterceptGuard>
  );
}
