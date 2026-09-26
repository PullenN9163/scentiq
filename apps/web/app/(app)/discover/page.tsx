import { DiscoverExperience } from "@/features/discover/discover-experience";
import { getDiscover } from "@/lib/server/queries";

export default async function DiscoverPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const filters = await searchParams;
  const results = await getDiscover({ family: filters.family, gender: filters.gender, season: filters.season, minimumValue: filters.minimum_value });
  return <DiscoverExperience results={results} />;
}
