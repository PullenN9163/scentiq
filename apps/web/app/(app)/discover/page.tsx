import { DiscoverExperience } from "@/features/discover/discover-experience";
import { getCollection, searchFragrances } from "@/lib/server/queries";
import { getDiscoveryIntelligence } from "@/lib/server/layering-actions";

export default async function DiscoverPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const filters = await searchParams;
  const query = filters.q?.trim() ?? "";
  const mode = ["balance", "taste", "explore", "seasonal"].includes(
    filters.mode ?? "",
  )
    ? (filters.mode ?? "balance")
    : "balance";
  const [collection, results, catalogResults] = await Promise.all([
    getCollection(),
    query
      ? Promise.resolve([])
      : getDiscoveryIntelligence({
          mode,
          family: filters.family,
          gender: filters.gender,
          season: filters.season,
          minimumValue: filters.minimum_value,
        }),
    query ? searchFragrances(query) : Promise.resolve([]),
  ]);
  return (
    <DiscoverExperience
      results={results}
      query={query}
      catalogResults={catalogResults}
      mode={mode}
      selectedSeason={filters.season}
      wishlistIds={collection
        .filter((item) => item.status === "wishlist")
        .map((item) => item.fragrance.id)}
    />
  );
}
