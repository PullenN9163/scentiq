import {PageHeader} from "@/components/shared/page-header";
import {LoadingState} from "@/components/shared/states";
import {DiscoverSearch} from "@/features/discover/discover-search";
import {DiscoverSkeleton} from "@/features/discover-atelier/discover-atelier";
import {isAtelierEnabled} from "@/lib/atelier-flag";
export default function DiscoverLoading() {
  if (isAtelierEnabled()) return <DiscoverSkeleton/>;
  return <section className="page"><PageHeader eyebrow="Beyond the shelf" title="Discover" description="Find your next favorite. Search the catalog while we consider your collection."/><DiscoverSearch/><LoadingState label="Finding recommendations" rows={3}/></section>;
}
