import { DiscoverExperience } from "@/features/discover/discover-experience";
import { getDiscover, searchFragrances } from "@/lib/server/queries";

export default async function DiscoverPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const filters = await searchParams;
  const query = filters.q?.trim() ?? "";
  const results = query ? [] : await getDiscover({ family: filters.family, gender: filters.gender, season: filters.season, minimumValue: filters.minimum_value });
  const catalogResults = query ? await searchFragrances(query) : [];
  return <DiscoverExperience results={results} query={query} catalogResults={catalogResults} />;
}
