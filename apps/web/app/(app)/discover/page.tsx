import { DiscoverExperience } from "@/features/discover/discover-experience";

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
