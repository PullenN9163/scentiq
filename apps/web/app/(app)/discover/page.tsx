import { DiscoverExperience } from "@/features/discover/discover-experience";
import { getCollection, searchFragrances } from "@/lib/server/queries";
import { getDiscoveryIntelligence } from "@/lib/server/layering-actions";
import { redirect } from "next/navigation";
import { ApiError } from "@/lib/server/api-client";

const fastDiscoveryEnabled = process.env.SCENTIQ_FAST_DISCOVERY_ENABLED?.toLowerCase() !== "false";

export default async function DiscoverPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const filters = await searchParams;
  const query = (filters.q ?? "").slice(0, 120);
  const mode = ["balance", "taste", "explore", "seasonal"].includes(filters.mode ?? "")
    ? filters.mode ?? "balance"
    : "balance";
  if (!fastDiscoveryEnabled) {
    const [collection, results, catalogResults] = await Promise.all([
        getCollection(),
        query.trim()
          ? Promise.resolve([])
          : getDiscoveryIntelligence({
              mode,
              season: filters.season,
              family: filters.family,
              gender: filters.gender,
              minimumValue: filters.minimum_value,
            }),
        query.trim() ? searchFragrances(query, 25, 0) : Promise.resolve([]),
      ]).catch((error: unknown) => {
      if (error instanceof ApiError && error.kind === "unauthorized") {
        redirect("/sign-in");
      }
      throw error;
      });
    return (
      <DiscoverExperience
        results={results}
        catalogResults={catalogResults}
        wishlistIds={collection.map((item) => item.fragrance.id)}
        query={query}
        mode={mode}
        selectedSeason={filters.season}
        selectedFamily={filters.family}
        selectedGender={filters.gender}
        selectedMinimumValue={filters.minimum_value}
        liveMode={false}
      />
    );
  }
  return (
    <DiscoverExperience
      results={[]}
      query={query}
      liveMode
      mode={mode}
      selectedSeason={filters.season}
      selectedFamily={filters.family}
      selectedGender={filters.gender}
      selectedMinimumValue={filters.minimum_value}
    />
  );
}
