"use client";

import Link from "next/link";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import {
  BookmarkPlus,
  Compass,
  Eye,
  Search,
  SlidersHorizontal,
} from "lucide-react";

import { CatalogImage } from "@/components/catalog-image";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { addToWishlist, searchCatalogPage } from "@/lib/server/actions";
import { DiscoverSearch } from "./discover-search";
import type { DiscoveryResult, FragranceSummary } from "@/types/api";

const percentage = (value: number) => `${Math.round(value * 100)}%`;
const emptyCatalog: FragranceSummary[] = [];

export function DiscoverExperience(props: Parameters<typeof DiscoverContent>[0]) {
  return <DiscoverContent key={JSON.stringify([props.query, props.mode, props.selectedSeason, props.selectedFamily, props.selectedGender, props.selectedMinimumValue])} {...props} />;
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
}) {
  const [matches, setMatches] = useState(catalogResults);
  const [hasMore, setHasMore] = useState(catalogResults.length === 25);
  const [previousResults, setPreviousResults] = useState(catalogResults);
  const [paginationError, setPaginationError] = useState<string | null>(null);
  if (previousResults !== catalogResults) {
    setPreviousResults(catalogResults);
    setMatches(catalogResults);
    setHasMore(catalogResults.length === 25);
    setPaginationError(null);
  }
  const [isLoadingMore, startLoadingMore] = useTransition();
  const isSearching = query.trim().length > 0;
  return (
    <section className="page">
      <PageHeader
        eyebrow="Beyond the shelf"
        title="Discover"
        description="Source-backed recommendations scored against your owned collection."
      />
      <DiscoverSearch query={query}/>
      {!isSearching ? (
        <form className="discover-filters" method="get">
          <SlidersHorizontal size={18} />
          <label>
            Discovery direction
            <select className="select" name="mode" defaultValue={mode}>
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
              defaultValue={selectedFamily}
              placeholder="Woody, Floral…"
            />
          </label>
          <label>
            Season
            <select
              className="select"
              name="season"
              defaultValue={selectedSeason}
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
            <select className="select" name="gender" defaultValue={selectedGender}>
              <option value="">All</option>
              <option value="female">Female</option>
              <option value="male">Male</option>
              <option value="unisex">Unisex</option>
            </select>
          </label>
          <label>
            Minimum value rating
            <select className="select" name="minimum_value" defaultValue={selectedMinimumValue}>
              <option value="">Any</option>
              <option value="3">3+</option>
              <option value="4">4+</option>
            </select>
          </label>
          <Button type="submit" variant="secondary">
            Apply filters
          </Button>
        </form>
      ) : null}
      {isSearching ? (
        matches.length ? (
          <>
            <p className="discover-result-count">
              Catalog results for “{query}”
            </p>
            <div className="discover-grid">
              {matches.map((item) => (
                <CatalogResultCard
                  key={item.id}
                  item={item}
                  query={query}
                  wishlistSaved={wishlistIds.includes(item.id)}
                  wishlistUnavailable={Boolean(wishlistError)}
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
                      try {
                      const more = await searchCatalogPage(
                        query,
                        matches.length,
                      );
                      setMatches((current) => {
                        const known = new Set(current.map(item => item.id));
                        return [...current, ...more.filter(item => !known.has(item.id))];
                      });
                      setHasMore(more.length === 25);
                      } catch {
                        setPaginationError("Could not load more fragrances. Your results are still here. Try again.");
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
        ) : (
          <Card>
            <CardContent className="empty-panel">
              <Search />
              <h2>No fragrances found for “{query}”</h2>
              <p>Try a fragrance name, brand, or concentration.</p>
            </CardContent>
          </Card>
        )
      ) : recommendationError ? (
        <Card><CardContent className="state-block" role="alert"><h2>Recommendations are taking a moment</h2><p className="muted">{recommendationError}</p><Button asChild variant="secondary"><Link href={`/discover?${new URLSearchParams({mode, family:selectedFamily, gender:selectedGender, season:selectedSeason, minimum_value:selectedMinimumValue})}`}>Try again</Link></Button></CardContent></Card>
      ) : results.length ? (
        <div className="discover-grid">
          {results.map((result) => {
            const item = result.fragrance;
            return (
              <Card
                key={item.id}
                className="discovery-card"
                data-testid="discovery-card"
              >
                <CatalogImage
                  className="discovery-card__art"
                  id={item.id}
                  name={item.name}
                  brand={item.brand.name}
                  imageUrl={item.image_url}
                />
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
                      initialSaved={wishlistIds.includes(item.id)}
                      unavailable={Boolean(wishlistError)}
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
      {wishlistError && <p role="status" className="data-note">{wishlistError}</p>}
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
