"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { Heart, Search, SlidersHorizontal, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState, useTransition } from "react";
import { toast } from "sonner";

import { Button } from "@/components/atelier/button";
import { Chip } from "@/components/atelier/chip";
import { FragranceCard } from "@/components/atelier/fragrance-card";
import { Plate } from "@/components/atelier/plate";
import { plateFragrance } from "@/components/atelier/plate-fragrance";
import { SegmentedControl } from "@/components/atelier/segmented-control";
import { Sheet } from "@/components/atelier/sheet";
import { AtelierEmpty } from "@/components/atelier/states";
import { useRegisterFragranceList } from "@/features/fragrance/fragrance-list-context";
import { accordFor, accordVars } from "@/lib/accord";
import { idleState } from "@/lib/action-state";
import { motionTokens } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { addToCollection, addToWishlist, searchCatalogPage } from "@/lib/server/actions";
import type { DiscoveryResult, FragranceSummary } from "@/types/api";

import { FAMILY_CHOICES, GENDER_CHOICES, MODES, SEASON_CHOICES, VALUE_CHOICES, detailHref, discoverHref, filterCount, reasonFor, suitsWords, toMode, type DiscoverFilters, type DiscoverMode } from "./discover-copy";
import { rememberSuits } from "./suits-memory";
import styles from "./discover-atelier.module.css";

const PAGE = 25;
class RequestError extends Error { constructor(readonly status: number) { super("Discover request failed"); } }
const unauthorized = (error: unknown) => error instanceof RequestError && error.status === 401;

/**
 * The Atelier Discover. Data handling follows DiscoverExperience: the live
 * feed and search endpoints (or the server-provided results when fast
 * discovery is off), the same URL parameters, wishlist status and paging.
 */
export function DiscoverAtelier({
  results: initialResults,
  catalogResults = [],
  query = "",
  mode = "balance",
  selectedSeason = "",
  selectedFamily = "",
  selectedGender = "",
  selectedMinimumValue = "",
  wishlistIds = [],
  liveMode = false,
  recommendationError,
}: {
  results: DiscoveryResult[];
  catalogResults?: FragranceSummary[];
  query?: string;
  mode?: string;
  selectedSeason?: string;
  selectedFamily?: string;
  selectedGender?: string;
  selectedMinimumValue?: string;
  wishlistIds?: string[];
  liveMode?: boolean;
  recommendationError?: string;
}) {
  const router = useRouter();
  const [activeQuery, setActiveQuery] = useState(query.slice(0, 120));
  const [filters, setFilters] = useState<DiscoverFilters>({ mode: toMode(mode), season: selectedSeason, family: selectedFamily, gender: selectedGender, minimum_value: selectedMinimumValue });
  const [draft, setDraft] = useState(filters);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [results, setResults] = useState(initialResults);
  const [matches, setMatches] = useState(catalogResults);
  const [hasMoreMatches, setHasMoreMatches] = useState(catalogResults.length === PAGE);
  const [hasMoreResults, setHasMoreResults] = useState(liveMode);
  const [feedError, setFeedError] = useState<string | undefined>(recommendationError);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [moreError, setMoreError] = useState<string | null>(null);
  const [busy, setBusy] = useState(Boolean(liveMode));
  const [sessionExpired, setSessionExpired] = useState(false);
  const [wishlist, setWishlist] = useState<string[]>(wishlistIds);
  const [wishlistUnavailable, setWishlistUnavailable] = useState(liveMode);
  const [loadingMore, startLoadingMore] = useTransition();
  const [attempt, setAttempt] = useState(0);
  const searchAbort = useRef<AbortController | null>(null);
  const feedAbort = useRef<AbortController | null>(null);
  const sequence = useRef(0);
  const searching = activeQuery.trim().length > 0;

  const writeUrl = useCallback((nextQuery: string, nextFilters: DiscoverFilters, push = false) => {
    window.history[push ? "pushState" : "replaceState"]({}, "", discoverHref(nextQuery, nextFilters));
  }, []);

  // Wishlist status for hearts (live mode reads it from the route handler).
  useEffect(() => {
    if (!liveMode) return;
    const controller = new AbortController();
    void fetch("/api/discover/wishlist", { signal: controller.signal, cache: "no-store" })
      .then(async (response) => { if (!response.ok) throw new RequestError(response.status); setWishlist(await response.json() as string[]); setWishlistUnavailable(false); })
      .catch((error) => { if (controller.signal.aborted) return; setWishlistUnavailable(true); if (unauthorized(error)) setSessionExpired(true); });
    return () => controller.abort();
  }, [liveMode]);

  // Feed or search, whichever applies, in live mode.
  useEffect(() => {
    if (!liveMode) return;
    searchAbort.current?.abort();
    feedAbort.current?.abort();
    const requestId = ++sequence.current;
    const controller = new AbortController();
    if (activeQuery.trim()) {
      searchAbort.current = controller;
      const timer = window.setTimeout(() => {
        setBusy(true);
        setSearchError(null);
        const params = new URLSearchParams({ q: activeQuery.trim().slice(0, 120), limit: String(PAGE), offset: "0", ...filters });
        void fetch(`/api/discover/search?${params}`, { signal: controller.signal, cache: "no-store" })
          .then(async (response) => { if (!response.ok) throw new RequestError(response.status); const data = await response.json() as FragranceSummary[]; if (requestId !== sequence.current) return; setMatches(data); setHasMoreMatches(data.length === PAGE); })
          .catch((error) => { if (controller.signal.aborted || requestId !== sequence.current) return; if (unauthorized(error)) setSessionExpired(true); else setSearchError("Search is temporarily unavailable. Your current results are still here. Try again."); })
          .finally(() => { if (requestId === sequence.current) setBusy(false); });
      }, 200);
      return () => { window.clearTimeout(timer); controller.abort(); };
    }
    feedAbort.current = controller;
    const params = new URLSearchParams({ ...filters, limit: String(PAGE), offset: "0" });
    const timer = window.setTimeout(() => {
      setBusy(true);
      void fetch(`/api/discover/feed?${params}`, { signal: controller.signal, cache: "no-store" })
        .then(async (response) => { if (!response.ok) throw new RequestError(response.status); const data = await response.json() as { items: DiscoveryResult[] }; if (requestId !== sequence.current) return; setResults(data.items); setHasMoreResults(data.items.length === PAGE); setFeedError(undefined); })
        .catch((error) => { if (controller.signal.aborted || requestId !== sequence.current) return; if (unauthorized(error)) setSessionExpired(true); else setFeedError("Your recommendations could not be loaded. You can still search the catalog or retry."); })
        .finally(() => { if (requestId === sequence.current) setBusy(false); });
    }, 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [activeQuery, filters, liveMode, attempt]);

  useRegisterFragranceList(searching ? matches.map((item) => item.id) : results.map((result) => result.fragrance.id));

  function changeMode(next: DiscoverMode) {
    const nextFilters = { ...filters, mode: next };
    if (liveMode) { setFilters(nextFilters); writeUrl(activeQuery, nextFilters, true); }
    else router.push(discoverHref(activeQuery, nextFilters));
  }

  function applyFilters() {
    setFiltersOpen(false);
    if (liveMode) { setFilters(draft); writeUrl(activeQuery, draft, true); }
    else router.push(discoverHref(activeQuery, draft));
  }

  function clearAll() {
    const cleared: DiscoverFilters = { mode: filters.mode, season: "", family: "", gender: "", minimum_value: "" };
    setDraft(cleared);
    if (liveMode) { setFilters(cleared); setActiveQuery(""); writeUrl("", cleared, true); }
    else router.push(discoverHref("", cleared));
  }

  function onQuery(value: string) {
    const next = value.slice(0, 120);
    setActiveQuery(next);
    if (liveMode) writeUrl(next, filters);
    if (!next.trim()) { searchAbort.current?.abort(); sequence.current++; setMatches([]); setHasMoreMatches(false); setSearchError(null); }
  }

  function showMore() {
    startLoadingMore(async () => {
      setMoreError(null);
      try {
        if (searching) {
          let more: FragranceSummary[];
          if (liveMode) {
            const params = new URLSearchParams({ q: activeQuery.trim(), limit: String(PAGE), offset: String(matches.length), ...filters });
            const response = await fetch(`/api/discover/search?${params}`, { cache: "no-store" });
            if (!response.ok) throw new RequestError(response.status);
            more = await response.json() as FragranceSummary[];
          } else more = await searchCatalogPage(activeQuery, matches.length);
          setMatches((current) => { const known = new Set(current.map((item) => item.id)); return [...current, ...more.filter((item) => !known.has(item.id))]; });
          setHasMoreMatches(more.length === PAGE);
        } else {
          const params = new URLSearchParams({ ...filters, limit: String(PAGE), offset: String(results.length) });
          const response = await fetch(`/api/discover/feed?${params}`, { cache: "no-store" });
          if (!response.ok) throw new RequestError(response.status);
          const more = (await response.json() as { items: DiscoveryResult[] }).items;
          setResults((current) => { const known = new Set(current.map((item) => item.fragrance.id)); return [...current, ...more.filter((item) => !known.has(item.fragrance.id))]; });
          setHasMoreResults(more.length === PAGE);
        }
      } catch (error) {
        if (unauthorized(error)) setSessionExpired(true);
        else setMoreError("Could not load more fragrances. Your results are still here. Try again.");
      }
    });
  }

  const [hero, ...rest] = results;
  const count = filterCount(filters);
  const markSaved = (id: string) => setWishlist((current) => (current.includes(id) ? current : [...current, id]));

  return (
    <div className="at-page" aria-busy={busy || loadingMore}>
      <h1 className={styles.title}>Discover</h1>
      <div className={styles.searchRow}>
        <label className={styles.search}>
          <Search aria-hidden="true" />
          <span className="sr-only">Search the catalog</span>
          <input type="search" value={activeQuery} placeholder="Search a fragrance, house or note" onChange={(event) => onQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !liveMode) router.push(discoverHref(activeQuery, filters)); }} />
          {activeQuery ? <button type="button" className={styles.clearSearch} aria-label="Clear search" onClick={() => { onQuery(""); if (!liveMode) router.push(discoverHref("", filters)); }}><X aria-hidden="true" /></button> : null}
        </label>
        <Button variant="soft" onClick={() => { setDraft(filters); setFiltersOpen(true); }}><SlidersHorizontal aria-hidden="true" />Filters{count ? ` · ${count}` : ""}</Button>
      </div>
      {!searching ? (
        <SegmentedControl<DiscoverMode> label="Discovery direction" className={styles.modes} value={filters.mode} onChange={changeMode} segments={MODES.map((entry) => ({ value: entry.value, label: entry.label, shortLabel: entry.shortLabel }))} />
      ) : null}
      {sessionExpired ? <p className="at-error" role="alert">Your session expired. <Link href="/sign-in">Sign in again</Link> to continue.</p> : null}

      {searching ? (
        matches.length > 0 ? (
          <section aria-label={`Catalog results for ${activeQuery}`}>
            <p className="at-caption" role="status">{busy ? `Searching for ${activeQuery}…` : `${matches.length} fragrances found for ${activeQuery}.`}</p>
            <ResultGrid items={matches.map((fragrance) => ({ fragrance }))} query={activeQuery} wishlist={wishlist} wishlistUnavailable={wishlistUnavailable} onSaved={markSaved} />
          </section>
        ) : busy ? (
          <p className="at-caption" role="status">Searching the catalog…</p>
        ) : searchError ? (
          <ErrorLine message={searchError} onRetry={() => { setSearchError(null); if (liveMode) setAttempt((value) => value + 1); else router.refresh(); }} />
        ) : (
          <AtelierEmpty title="Nothing matches" action={<Button variant="text" onClick={clearAll}>Clear filters</Button>}>Try a fragrance name, house or note.</AtelierEmpty>
        )
      ) : feedError ? (
        <ErrorLine message={feedError} onRetry={() => (liveMode ? setAttempt((value) => value + 1) : router.refresh())} title="Recommendations are taking a moment" />
      ) : hero ? (
        <>
          <AnimatePresence mode="wait" initial={false}>
            <motion.div key={`${filters.mode}-${hero.fragrance.id}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ ...motionTokens.settle, duration: 0.15 }}>
              <DiscoverHero result={hero} saved={wishlist.includes(hero.fragrance.id)} wishlistUnavailable={wishlistUnavailable} onSaved={markSaved} />
            </motion.div>
          </AnimatePresence>
          {rest.length > 0 ? (
            <section className={styles.more} aria-labelledby="more-for-you">
              <h2 id="more-for-you" className="at-title">More for you</h2>
              <ResultGrid items={rest} wishlist={wishlist} wishlistUnavailable={wishlistUnavailable} onSaved={markSaved} />
            </section>
          ) : null}
        </>
      ) : busy ? (
        <DiscoverSkeleton inline />
      ) : (
        <AtelierEmpty title="Nothing matches" action={count ? <Button variant="text" onClick={clearAll}>Clear filters</Button> : <Button asChild variant="outline"><Link href="/collection">Add fragrances</Link></Button>}>
          {count ? "Broaden the filters to see more." : "Add owned fragrances and ScentIQ can suggest what comes next. It will not invent a match."}
        </AtelierEmpty>
      )}

      {(searching ? hasMoreMatches && matches.length > 0 : hasMoreResults && results.length > 0 && !feedError) ? (
        <div className={styles.showMore}>
          <Button variant="outline" disabled={loadingMore} onClick={showMore}>{loadingMore ? "Loading…" : "Show more"}</Button>
          {moreError ? <p className="at-error" role="alert">{moreError}</p> : null}
        </div>
      ) : null}
      {wishlistUnavailable && liveMode ? <p className="at-caption" role="status">Wishlist status is temporarily unavailable. Hearts return when it is back.</p> : null}

      <Sheet
        open={filtersOpen}
        onOpenChange={setFiltersOpen}
        title="Filters"
        footer={<div className={styles.sheetActions}><Button onClick={applyFilters}>Apply</Button><Button variant="text" onClick={() => setDraft({ ...draft, season: "", family: "", gender: "", minimum_value: "" })}>Clear</Button></div>}
      >
        <div className={styles.filterGroups}>
          <ChoiceGroup label="Family" options={FAMILY_CHOICES.map((family) => [family, family])} value={draft.family} onChange={(family) => setDraft({ ...draft, family })} />
          <ChoiceGroup label="Season" options={SEASON_CHOICES} value={draft.season} onChange={(season) => setDraft({ ...draft, season })} />
          <ChoiceGroup label="Gender" options={GENDER_CHOICES} value={draft.gender} onChange={(gender) => setDraft({ ...draft, gender })} />
          <ChoiceGroup label="Minimum value rating" options={VALUE_CHOICES} value={draft.minimum_value} onChange={(minimum_value) => setDraft({ ...draft, minimum_value })} />
        </div>
      </Sheet>
    </div>
  );
}

function ChoiceGroup({ label, options, value, onChange }: { label: string; options: [string, string][]; value: string; onChange: (value: string) => void }) {
  return (
    <fieldset className={styles.group}>
      <legend className="at-label">{label}</legend>
      <div className={styles.chips}>
        {options.map(([option, text]) => <Chip key={option} variant="choice" pressed={value === option} onClick={() => onChange(value === option ? "" : option)}>{text}</Chip>)}
      </div>
    </fieldset>
  );
}

function ErrorLine({ message, onRetry, title }: { message: string; onRetry: () => void; title?: string }) {
  return (
    <section className={styles.error} role="alert">
      {title ? <h2 className="at-title">{title}</h2> : null}
      <p className="at-error">{message}</p>
      <Button variant="outline" onClick={onRetry}>Try again</Button>
    </section>
  );
}

function HeartButton({ fragranceId, name, saved, unavailable, onSaved }: { fragranceId: string; name: string; saved: boolean; unavailable: boolean; onSaved: (id: string) => void }) {
  const [pending, startTransition] = useTransition();
  function save() {
    if (saved || pending || unavailable) return;
    const data = new FormData();
    data.set("fragrance_id", fragranceId);
    startTransition(async () => {
      try { await addToWishlist(data); onSaved(fragranceId); toast.success("Saved to wishlist"); }
      catch { toast.error("Could not save to your wishlist. Please try again."); }
    });
  }
  return (
    <button type="button" className={styles.heart} data-saved={saved ? "true" : "false"} aria-pressed={saved} aria-label={saved ? `${name} is on your wishlist` : `Add ${name} to wishlist`} disabled={pending || unavailable} onClick={save}>
      <Heart aria-hidden="true" />
    </button>
  );
}

function ResultGrid({ items, query, wishlist, wishlistUnavailable, onSaved }: { items: Array<Pick<DiscoveryResult, "fragrance"> & Partial<DiscoveryResult>>; query?: string; wishlist: string[]; wishlistUnavailable: boolean; onSaved: (id: string) => void }) {
  return (
    <motion.ul layout className={styles.grid}>
      {items.map((item) => (
        <motion.li key={item.fragrance.id} layout transition={motionTokens.quick}>
          <FragranceCard
            fragrance={plateFragrance(item.fragrance)}
            accord={accordFor(item.fragrance)}
            href={detailHref(item.fragrance.id, query)}
            onOpen={() => { if (item.taste_match !== undefined && item.collection_expansion !== undefined) rememberSuits(item.fragrance.id, suitsWords(item as DiscoveryResult)); }}
            corner={<HeartButton fragranceId={item.fragrance.id} name={item.fragrance.name} saved={wishlist.includes(item.fragrance.id)} unavailable={wishlistUnavailable} onSaved={onSaved} />}
          />
        </motion.li>
      ))}
    </motion.ul>
  );
}

function DiscoverHero({ result, saved, wishlistUnavailable, onSaved }: { result: DiscoveryResult; saved: boolean; wishlistUnavailable: boolean; onSaved: (id: string) => void }) {
  const router = useRouter();
  const fragrance = result.fragrance;
  const accord = accordFor(fragrance);
  const [pending, startTransition] = useTransition();
  const [owned, setOwned] = useState(false);
  const href = detailHref(fragrance.id);
  const remember = () => rememberSuits(fragrance.id, suitsWords(result));
  function wishlist() {
    const data = new FormData();
    data.set("fragrance_id", fragrance.id);
    startTransition(async () => {
      try { await addToWishlist(data); onSaved(fragrance.id); toast.success("Saved to wishlist"); }
      catch { toast.error("Could not save to your wishlist. Please try again."); }
    });
  }
  function own() {
    const data = new FormData();
    data.set("fragrance_id", fragrance.id);
    data.set("status", "owned");
    data.set("ownership_type", "bottle");
    startTransition(async () => {
      const response = await addToCollection(idleState, data);
      if (response.status === "error") { toast.error(response.message ?? "Could not add it to your shelf. Try again."); return; }
      setOwned(true);
      toast.success("Added to your shelf");
      router.refresh();
    });
  }
  return (
    <section className={styles.hero} style={accordVars(accord)} aria-labelledby="discover-hero-name" data-testid="discover-hero">
      <div className={styles.heroCopy}>
        <p className="at-overline">{fragrance.brand.name}</p>
        <h2 id="discover-hero-name" className={styles.heroName}><Link href={href} onClick={remember}>{fragrance.name}</Link></h2>
        <p className={cn("at-body-lg", styles.heroReason)}>{reasonFor(result)}</p>
        <div className={styles.heroActions}>
          <Button disabled={pending || saved || wishlistUnavailable} onClick={wishlist}>{saved ? "On your wishlist" : pending ? "Saving…" : "Add to wishlist"}</Button>
          <Button variant="soft" disabled={pending || owned} onClick={own}>{owned ? "On your shelf" : "I own this"}</Button>
        </div>
      </div>
      <Link href={href} onClick={remember} className={styles.heroPlate} aria-label={`Open ${fragrance.name}`}>
        <Plate fragrance={plateFragrance(fragrance)} accord={accord} className={styles.plate} priority layoutId={`plate-${fragrance.id}`} sizes="(max-width: 700px) 90vw, 300px" />
      </Link>
    </section>
  );
}

export function DiscoverSkeleton({ inline = false }: { inline?: boolean }) {
  const body = (
    <>
      <span className={cn("at-skeleton", styles.skeletonHero)} />
      <div className={styles.grid}>
        {Array.from({ length: 8 }, (_, index) => <span key={index} className="at-skeleton" style={{ aspectRatio: "4 / 5" }} />)}
      </div>
    </>
  );
  if (inline) return <div aria-hidden="true">{body}</div>;
  return (
    <div className="at-page" aria-busy="true">
      <span className="sr-only" role="status">Finding recommendations</span>
      <span className="at-skeleton" style={{ width: 220, height: 48, marginBottom: 24 }} />
      {body}
    </div>
  );
}
