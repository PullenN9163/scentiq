import { DiscoverExperience } from "@/features/discover/discover-experience";
import { getCollection, searchFragrances } from "@/lib/server/queries";
import { getDiscoveryIntelligence } from "@/lib/server/layering-actions";
import { ApiError } from "@/lib/server/api-client";
import { redirect } from "next/navigation";

async function optionalRead<T>(read: Promise<T>): Promise<{data?: T; failed: boolean}> {
  try { return {data: await read, failed: false}; }
  catch (error) {
    if (error instanceof ApiError && error.kind === "unauthorized") redirect("/sign-in");
    if (error instanceof ApiError && error.kind === "forbidden") throw error;
    console.error("Discover optional read failed", error instanceof ApiError ? {kind:error.kind, status:error.status, code:error.code, requestId:error.requestId} : {kind:"unknown"});
    return {failed:true};
  }
}

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
    optionalRead(getCollection()),
    query
      ? Promise.resolve({data: [], failed:false})
      : optionalRead(getDiscoveryIntelligence({
          mode,
          family: filters.family,
          gender: filters.gender,
          season: filters.season,
          minimumValue: filters.minimum_value,
        })),
    query ? searchFragrances(query) : Promise.resolve([]),
  ]);
  return (
    <DiscoverExperience
      results={results.data ?? []}
      query={query}
      catalogResults={catalogResults}
      mode={mode}
      selectedSeason={filters.season}
      selectedFamily={filters.family}
      selectedGender={filters.gender}
      selectedMinimumValue={filters.minimum_value}
      recommendationError={results.failed ? "Your recommendations could not be loaded. You can still search the catalog or retry." : undefined}
      wishlistError={collection.failed ? "Wishlist status is temporarily unavailable. Refresh before saving an existing entry." : undefined}
      wishlistIds={(collection.data ?? [])
        .filter((item) => item.status === "wishlist")
        .map((item) => item.fragrance.id)}
    />
  );
}
