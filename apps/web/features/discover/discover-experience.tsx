"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import {
  BookmarkPlus,
  Compass,
  Eye,
  Search,
  SlidersHorizontal,
  Sparkles, ArrowUpRight, Heart, Layers, Sun, LayoutGrid, List, ChevronDown,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { ExperienceBackdrop } from "@/components/shared/experience";
import "./discover.css";

import { CatalogImage } from "@/components/catalog-image";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { addToWishlist, searchCatalogPage } from "@/lib/server/actions";
import { SurfaceOptions } from "@/features/recommendations/surface-options";
import { DiscoverSearch } from "./discover-search";
import type { DiscoveryResult, FragranceSummary } from "@/types/api";

const percentage = (value: number) => `${Math.round(value * 100)}%`;
const emptyCatalog: FragranceSummary[] = [];

class DiscoverRequestError extends Error {
  constructor(readonly status: number) { super("Discover request failed"); }
}
const isUnauthorized = (error: unknown) => error instanceof DiscoverRequestError && error.status === 401;

export function DiscoverExperience(props: Parameters<typeof DiscoverContent>[0]) {
  const staticKey = props.liveMode ? undefined : JSON.stringify([props.query, props.mode, props.selectedSeason, props.selectedFamily, props.selectedGender, props.selectedMinimumValue]);
  return <DiscoverContent key={staticKey} {...props} />;
}

function DiscoverContent({
  results,
  query = "",
  catalogResults = emptyCatalog,
  mode = "balance",
  selectedSeason = "",
  wishlistIds = [],
  selectedFamily = "",
  selectedGender = "",
  selectedMinimumValue = "",
  recommendationError,
  wishlistError,
  liveMode = false,
  initialRefreshStatus,
}: {
  results: DiscoveryResult[];
  query?: string;
  catalogResults?: FragranceSummary[];
  mode?: string;
  selectedSeason?: string;
  wishlistIds?: string[];
  selectedFamily?: string;
  selectedGender?: string;
  selectedMinimumValue?: string;
  recommendationError?: string;
  wishlistError?: string;
  liveMode?: boolean;
  initialRefreshStatus?: string;
}) {
  const [activeQuery, setActiveQuery] = useState(query.slice(0, 120));
  const [activeFilters, setActiveFilters] = useState({mode, season:selectedSeason, family:selectedFamily, gender:selectedGender, minimum_value:selectedMinimumValue});
  const [activeWishlist, setActiveWishlist] = useState(wishlistIds);
  const [wishlistUnavailable, setWishlistUnavailable] = useState(Boolean(wishlistError) || liveMode);
  const [liveRecommendationError, setLiveRecommendationError] = useState<string | undefined>(recommendationError);
  const [refreshStatus, setRefreshStatus] = useState(initialRefreshStatus);
  const [busy, setBusy] = useState(Boolean(liveMode && query.trim()));
  const [searchError, setSearchError] = useState<string | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);
  const [matches, setMatches] = useState(catalogResults);
  const [hasMore, setHasMore] = useState(catalogResults.length === 25);
  const [paginationError, setPaginationError] = useState<string | null>(null);
  const [displayedResults,setDisplayedResults] = useState(results);
  const searchAbort = useRef<AbortController | null>(null);
  const feedAbort = useRef<AbortController | null>(null);
  const sequence = useRef(0);
  const paginationSequence = useRef(0);
  const filters = activeFilters;
  const isSearching = activeQuery.trim().length > 0;
  const writeUrl = useCallback((nextQuery: string, nextFilters = filters, push = false) => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams();
    if (nextQuery.trim()) params.set("q", nextQuery.trim().slice(0, 120));
    if (nextFilters.mode !== "balance") params.set("mode", nextFilters.mode);
    if (nextFilters.family) params.set("family", nextFilters.family);
    if (nextFilters.season) params.set("season", nextFilters.season);
    if (nextFilters.gender) params.set("gender", nextFilters.gender);
    if (nextFilters.minimum_value) params.set("minimum_value", nextFilters.minimum_value);
    const href = `/discover${params.size ? `?${params}` : ""}`;
    window.history[push ? "pushState" : "replaceState"]({}, "", href);
  }, [filters]);
  const search = useCallback(async (value: string, immediate = false) => {
    const normalized = value.trim().slice(0, 120);
    searchAbort.current?.abort();
    const requestId = ++sequence.current;
    if (!normalized) { setBusy(false); setSearchError(null); setMatches([]); setHasMore(false); return; }
    const controller = new AbortController(); searchAbort.current = controller;
    try {
      await new Promise<void>((resolve) => window.setTimeout(resolve, immediate ? 0 : 200));
      if (controller.signal.aborted) return;
      setBusy(true); setSearchError(null);
      const params = new URLSearchParams({q:normalized, limit:"25", offset:"0", ...filters});
      const response = await fetch(`/api/discover/search?${params}`, {signal:controller.signal, cache:"no-store"});
      if (!response.ok) throw new DiscoverRequestError(response.status);
      const data = await response.json() as FragranceSummary[];
      if (controller.signal.aborted || requestId !== sequence.current) return;
      setMatches(data); setHasMore(data.length === 25); setPaginationError(null);
    } catch (error) {
      if (!controller.signal.aborted && requestId === sequence.current) {
        if (isUnauthorized(error)) setSessionExpired(true);
        else setSearchError("Search is temporarily unavailable. Your current results are still here. Try again.");
      }
    }
    finally { if (requestId === sequence.current) setBusy(false); }
  }, [filters]);
  useEffect(() => {
    if (!liveMode) return;
    const onPopState = () => {
      const params = new URLSearchParams(window.location.search);
      const nextQuery = (params.get("q") ?? "").slice(0, 120);
      setActiveQuery(nextQuery);
      setBusy(Boolean(nextQuery.trim()));
      setActiveFilters({mode:params.get("mode") ?? "balance", season:params.get("season") ?? "", family:params.get("family") ?? "", gender:params.get("gender") ?? "", minimum_value:params.get("minimum_value") ?? ""});
    };
    window.addEventListener("popstate", onPopState);
    const controller = new AbortController();
    void fetch("/api/discover/wishlist", {signal:controller.signal, cache:"no-store"}).then(async response => {if (!response.ok) throw new DiscoverRequestError(response.status); setActiveWishlist(await response.json() as string[]); setWishlistUnavailable(false);}).catch(error=>{setWishlistUnavailable(true);if(isUnauthorized(error))setSessionExpired(true);});
    return () => { window.removeEventListener("popstate", onPopState); controller.abort(); };
  }, [liveMode]);
  useEffect(() => {
    if (!liveMode) return;
    searchAbort.current?.abort(); feedAbort.current?.abort();
    if (activeQuery.trim()) {
      const schedule = window.setTimeout(()=>void search(activeQuery),0);
      return ()=>{window.clearTimeout(schedule);searchAbort.current?.abort();};
    }
    const controller = new AbortController(); feedAbort.current = controller;
    const params = new URLSearchParams({...filters, limit:"25", offset:"0"});
    void fetch(`/api/discover/feed?${params}`, {signal:controller.signal, cache:"no-store"}).then(async response => {
      if (!response.ok) throw new DiscoverRequestError(response.status);
      const data = await response.json() as {items:DiscoveryResult[];refresh_status:string};
      if (!controller.signal.aborted) { setDisplayedResults(data.items); setRefreshStatus(data.refresh_status); setLiveRecommendationError(undefined); }
    }).catch(error=>{if (!controller.signal.aborted) {if(isUnauthorized(error))setSessionExpired(true);else setLiveRecommendationError("Your recommendations could not be loaded. You can still search the catalog or retry.");}});
    return () => controller.abort();
  }, [activeQuery, filters, liveMode, search]);
  const selectDiscovery = useCallback((choice: DiscoveryResult | import("@/types/layering").LayeringStackSuggestion) => {
    if ("fragrance" in choice) setDisplayedResults(previous=>[choice,...previous.filter(item=>item.fragrance.id !== choice.fragrance.id)]);
  },[setDisplayedResults]);
  const [compact, setCompact] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(Boolean(filters.family || filters.season || filters.gender || filters.minimum_value));
  const reducedMotion = useReducedMotion();
  const directionHref = (direction: string) => {
    const params = new URLSearchParams({ mode: direction });
    if (filters.family) params.set("family", filters.family);
    if (filters.season) params.set("season", filters.season);
    if (filters.gender) params.set("gender", filters.gender);
    if (filters.minimum_value) params.set("minimum_value", filters.minimum_value);
    return `/discover?${params}`;
  };
  const [previousResults, setPreviousResults] = useState(catalogResults);
  if (previousResults !== catalogResults) {
    setPreviousResults(catalogResults);
    setMatches(catalogResults);
    setHasMore(catalogResults.length === 25);
    setPaginationError(null);
  }
  const [isLoadingMore, startLoadingMore] = useTransition();
  const paginationController = useRef<AbortController | null>(null);
  useEffect(()=>{paginationController.current?.abort();paginationSequence.current++;},[activeQuery,filters]);
  return (
    <section className={`page experience-page discovery-experience ${compact ? "discovery-experience--compact" : ""}`} aria-busy={busy || isLoadingMore}>
      <ExperienceBackdrop tone="discover" />
      <PageHeader
        eyebrow="Beyond the shelf"
        title="Discover"
        description="Source-backed recommendations scored against your owned collection."
      />
      <div className="discovery-toolbar">
        <DiscoverSearch query={activeQuery} onChange={(value)=>{const next=value.slice(0,120); setActiveQuery(next); writeUrl(next); if(!next.trim()){searchAbort.current?.abort();paginationController.current?.abort();sequence.current++;setBusy(false);setSearchError(null);setMatches([]);setHasMore(false);}else setBusy(true);}} onSubmit={()=>void search(activeQuery,true)} onClear={()=>{searchAbort.current?.abort(); paginationController.current?.abort(); sequence.current++; setActiveQuery(""); setBusy(false); setSearchError(null); setMatches([]); setHasMore(false); writeUrl("",filters,true);}}/>
        <div className="discovery-toolbar__actions">
          <Button type="button" variant="secondary" aria-expanded={filtersOpen} aria-controls="discovery-filter-panel" onClick={() => setFiltersOpen(!filtersOpen)}><SlidersHorizontal size={16} />More filters<ChevronDown size={14} className={filtersOpen ? "discovery-chevron--open" : ""} /></Button>
          <div className="discovery-view-switch" aria-label="Result layout"><Button type="button" variant="ghost" aria-label="Gallery view" aria-pressed={!compact} onClick={() => setCompact(false)}><LayoutGrid size={16}/></Button><Button type="button" variant="ghost" aria-label="Compact view" aria-pressed={compact} onClick={() => setCompact(true)}><List size={16}/></Button></div>
        </div>
      </div>
      {!isSearching && <nav className="discovery-directions" aria-label="Discovery directions">
        {[{value:"balance",title:"Balance my collection",description:"Find the missing piece",icon:Layers},{value:"taste",title:"More of what I love",description:"Follow your signature",icon:Heart},{value:"explore",title:"Explore something new",description:"Step beyond the familiar",icon:Sparkles},{value:"seasonal",title:"Prepare for a season",description:"Meet your next season",icon:Sun}].map(({value,title,description,icon:Icon}) => <Link key={value} href={directionHref(value)} aria-label={title} aria-current={filters.mode === value ? "page" : undefined} className="discovery-direction"><Icon size={20} aria-hidden="true" /><strong>{title}</strong><span>{description}</span><ArrowUpRight className="discovery-direction__arrow" size={16} aria-hidden="true" /></Link>)}
      </nav>}
      {sessionExpired && <p role="alert" className="field-error">Your session expired. <Link href="/sign-in">Sign in again</Link> to continue.</p>}
      <form id="discovery-filter-panel" className="discover-filters" method="get" onSubmit={event=>{event.preventDefault();writeUrl(activeQuery,filters,true);}} hidden={!filtersOpen}>
          <SlidersHorizontal size={18} />
          <label>
            Discovery direction
            <select className="select" name="mode" value={filters.mode} onChange={event=>{const next={...filters,mode:event.target.value};setActiveFilters(next);writeUrl(activeQuery,next,true);}}>
              <option value="balance">Balance my collection</option>
              <option value="taste">More of what I love</option>
              <option value="explore">Explore something new</option>
              <option value="seasonal">Prepare for a season</option>
            </select>
          </label>
          <label>
            Family
            <input
              className="input"
              name="family"
              value={filters.family}
              onChange={event=>{const next={...filters,family:event.target.value};setActiveFilters(next);writeUrl(activeQuery,next,true);}}
              placeholder="Woody, Floral…"
            />
          </label>
          <label>
            Season
            <select
              className="select"
              name="season"
              value={filters.season}
              onChange={event=>{const next={...filters,season:event.target.value};setActiveFilters(next);writeUrl(activeQuery,next,true);}}
            >
              <option value="">All</option>
              <option value="spring">Spring</option>
              <option value="summer">Summer</option>
              <option value="fall">Fall</option>
              <option value="winter">Winter</option>
            </select>
          </label>
          <label>
            Gender
            <select className="select" name="gender" value={filters.gender} onChange={event=>{const next={...filters,gender:event.target.value};setActiveFilters(next);writeUrl(activeQuery,next,true);}}>
              <option value="">All</option>
              <option value="female">Female</option>
              <option value="male">Male</option>
              <option value="unisex">Unisex</option>
            </select>
          </label>
          <label>
            Minimum value rating
          <select className="select" name="minimum_value" value={filters.minimum_value} onChange={event=>{const next={...filters,minimum_value:event.target.value};setActiveFilters(next);writeUrl(activeQuery,next,true);}}>
              <option value="">Any</option>
              <option value="3">3+</option>
              <option value="4">4+</option>
            </select>
          </label>
          <Button type="submit" variant="secondary">
            Apply filters
          </Button>
      </form>
      {!isSearching && !liveRecommendationError && displayedResults.length > 0 && <SurfaceOptions surface="discovery" parameters={{mode:filters.mode,...(filters.family?{family:filters.family}:{}),...(filters.season?{season:filters.season}:{}),...(filters.gender?{gender:filters.gender}:{}),...(filters.minimum_value?{minimum_value:Number(filters.minimum_value)}:{})}} onChoice={selectDiscovery}/>}
      {isSearching ? (
        matches.length ? (
          <>
            <p className="discover-result-count">
              Catalog results for “{activeQuery}”
            </p>
            <div className="discover-grid">
              {matches.map((item) => (
                <CatalogResultCard
                  key={item.id}
                  item={item}
                  query={activeQuery}
                  wishlistSaved={activeWishlist.includes(item.id)}
                  wishlistUnavailable={wishlistUnavailable}
                />
              ))}
            </div>
            {hasMore ? (
              <div className="discover-load-more">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={isLoadingMore}
                  onClick={() =>
                    startLoadingMore(async () => {
                      setPaginationError(null);
                      let controller:AbortController|null=null;
                      let requestId=0;
                      try {
                      paginationController.current?.abort();
                      controller=new AbortController();paginationController.current=controller;
                      requestId=++paginationSequence.current;
                      let more:FragranceSummary[];
                      if (liveMode) {
                        const params=new URLSearchParams({q:activeQuery.trim(),limit:"25",offset:String(matches.length),...filters});
                        const response=await fetch(`/api/discover/search?${params}`,{signal:controller.signal,cache:"no-store"});
                        if(!response.ok)throw new DiscoverRequestError(response.status);
                        more=await response.json() as FragranceSummary[];
                      } else more=await searchCatalogPage(activeQuery,matches.length);
                      if(!controller || controller.signal.aborted || paginationController.current!==controller || requestId!==paginationSequence.current)return;
                      setMatches((current) => {
                        const known = new Set(current.map(item => item.id));
                        return [...current, ...more.filter(item => !known.has(item.id))];
                      });
                      setHasMore(more.length === 25);
                      } catch (error) {
                        if(!controller || controller.signal.aborted || paginationController.current!==controller || requestId!==paginationSequence.current)return;
                        if(isUnauthorized(error))setSessionExpired(true);
                        else setPaginationError("Could not load more fragrances. Your results are still here. Try again.");
                      }
                    })
                  }
                >
                  {isLoadingMore ? "Loading…" : "Load more"}
                </Button>
                {paginationError && <p role="alert" className="field-error">{paginationError}</p>}
              </div>
            ) : null}
          </>
        ) : busy ? <p role="status">Searching the catalog…</p> : (
          <Card>
            <CardContent className="empty-panel">
              <Search />
              <h2>No fragrances found for “{activeQuery}”</h2>
              <p>Try a fragrance name, brand, or concentration.</p>
            </CardContent>
          </Card>
        )
      ) : liveRecommendationError ? (
        <Card><CardContent className="state-block" role="alert"><h2>Recommendations are taking a moment</h2><p className="muted">{liveRecommendationError}</p><Button asChild variant="secondary"><Link href={`/discover?${new URLSearchParams({mode:filters.mode, family:filters.family, gender:filters.gender, season:filters.season, minimum_value:filters.minimum_value})}`}>Try again</Link></Button></CardContent></Card>
      ) : displayedResults.length ? (
        <div className="discover-grid">
          {displayedResults.map((result, index) => {
            const item = result.fragrance;
            return (
              <Card
                key={item.id}
                className={`discovery-card ${index === 0 ? "discovery-featured" : ""}`}
                data-testid="discovery-card"
              >
                <motion.div className="discovery-art-stage" initial={false} whileHover={reducedMotion ? undefined : { scale: 1.025 }} transition={{ type:"spring", stiffness:180, damping:24 }}>
                {index === 0 && <span className="discovery-featured__label"><Sparkles size={14} />Featured discovery</span>}
                <CatalogImage
                  className="discovery-card__art"
                  id={item.id}
                  name={item.name}
                  brand={item.brand.name}
                  imageUrl={item.image_url}
                  priority={index === 0}
                  sizes={index === 0 ? "(max-width: 640px) 76vw, (max-width: 1200px) 46vw, 500px" : undefined}
                />
                </motion.div>
                <CardContent>
                  <p className="eyebrow">
                    {item.olfactory_family ?? "Family not recorded"} ·{" "}
                    {item.gender ?? "Unlabelled"}
                  </p>
                  <h2 className="serif">{item.name}</h2>
                  <p>{item.brand.name}</p>
                  <div className="cluster">
                    {item.top_accords.map((accord) => (
                      <Badge key={accord}>{accord}</Badge>
                    ))}
                  </div>
                  <p>
                    {item.rating_average === null
                      ? "Not enough community data"
                      : `★ ${item.rating_average.toFixed(2)} (${item.rating_count ?? "vote count unknown"})`}
                  </p>
                  {result.reasons?.length ? <p>{result.reasons[0]}</p> : null}
                  {result.evidence_coverage != null ? (
                    <p className="data-note">
                      {percentage(result.evidence_coverage)} catalog evidence
                      {result.season_fit != null
                        ? ` · ${percentage(result.season_fit)} selected-season fit`
                        : ""}
                    </p>
                  ) : null}
                  <dl className="score-list">
                    <div>
                      <dt>Taste match</dt>
                      <dd>{percentage(result.taste_match)}</dd>
                    </div>
                    <div>
                      <dt>Collection expansion</dt>
                      <dd>{percentage(result.collection_expansion)}</dd>
                    </div>
                    <div>
                      <dt>Redundancy risk</dt>
                      <dd>{percentage(result.redundancy_risk)}</dd>
                    </div>
                  </dl>
                  <div className="cluster">
                    <Button asChild variant="secondary">
                      <Link href={detailHref(item.id)}>
                        <Eye size={16} />
                        View details
                      </Link>
                    </Button>
                    <WishlistButton
                      fragranceId={item.id}
                      initialSaved={activeWishlist.includes(item.id)}
                      unavailable={wishlistUnavailable}
                    />
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      ) : (
        <Card>
          <CardContent className="empty-panel">
            <Compass />
            <h2>No recommendations yet</h2>
            <p>
              Add owned fragrances or broaden the filters. ScentIQ will not
              invent a match.
            </p>
          </CardContent>
        </Card>
      )}
      {isSearching && <p role="status" aria-live="polite">{busy ? `Searching for ${activeQuery}…` : searchError ? searchError : `${matches.length} fragrances found for ${activeQuery}.`}</p>}
      {searchError && <Button type="button" variant="secondary" onClick={()=>void search(activeQuery,true)}>Retry search</Button>}
      {!isSearching && refreshStatus && <p className="data-note" aria-live="polite">{refreshStatus === "pending" ? "Recommendations are being refreshed." : refreshStatus === "fallback" ? "Showing your latest available recommendations." : "Recommendations are up to date."}</p>}
      {wishlistUnavailable && <p role="status" className="data-note">Wishlist status is temporarily unavailable. Refresh before saving an existing entry.</p>}
    </section>
  );
}

function CatalogResultCard({
  item,
  query,
  wishlistSaved,
  wishlistUnavailable,
}: {
  item: FragranceSummary;
  query: string;
  wishlistSaved: boolean;
  wishlistUnavailable?: boolean;
}) {
  return (
    <Card className="discovery-card" data-testid="catalog-result-card">
      <CatalogImage
        className="discovery-card__art"
        id={item.id}
        name={item.name}
        brand={item.brand.name}
        imageUrl={item.image_url}
      />
      <CardContent>
        <p className="eyebrow">{formatConcentration(item.concentration)}</p>
        <h2 className="serif">{item.name}</h2>
        <p>{item.brand.name}</p>
        <div className="cluster">
          {item.top_accords.map((accord) => (
            <Badge key={accord}>{accord}</Badge>
          ))}
        </div>
        <p>
          {item.rating_average === null
            ? "Not enough community data"
            : `★ ${item.rating_average.toFixed(2)} (${item.rating_count ?? "vote count unknown"})`}
        </p>
        <div className="cluster">
          <Button asChild variant="secondary">
            <Link href={detailHref(item.id, query)}>
              <Eye size={16} />
              View details
            </Link>
          </Button>
          <WishlistButton fragranceId={item.id} initialSaved={wishlistSaved} unavailable={wishlistUnavailable}/>
        </div>
      </CardContent>
    </Card>
  );
}

function WishlistButton({
  fragranceId,
  initialSaved,
  unavailable = false,
}: {
  fragranceId: string;
  initialSaved: boolean;
  unavailable?: boolean;
}) {
  const [added, setAdded] = useState(false);
  const [pending, startTransition] = useTransition();
  const saved = initialSaved || added;
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (saved || pending || unavailable) return;
        const data = new FormData(event.currentTarget);
        startTransition(async () => {
          try {
            await addToWishlist(data);
            setAdded(true);
            toast.success("Saved to wishlist");
          } catch {
            toast.error("Could not save to your wishlist. Please try again.");
          }
        });
      }}
    >
      <input type="hidden" name="fragrance_id" value={fragranceId} />
      <Button type="submit" disabled={saved || pending || unavailable}>
        <BookmarkPlus size={16} />
        {saved ? "Saved to wishlist" : unavailable ? "Wishlist unavailable" : pending ? "Saving…" : "Add to wishlist"}
      </Button>
    </form>
  );
}

function detailHref(fragranceId: string, query?: string): string {
  const parameters = new URLSearchParams({ from: "discover" });
  if (query?.trim()) parameters.set("q", query.trim());
  return `/collection/${fragranceId}?${parameters.toString()}`;
}

function formatConcentration(value: string | null): string {
  if (!value) return "Concentration not recorded";
  const words = value.replaceAll("_", " ").toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}
