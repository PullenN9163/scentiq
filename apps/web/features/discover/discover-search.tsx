import Link from "next/link";
import {Search} from "lucide-react";
import {Button} from "@/components/ui/button";

export function DiscoverSearch({query=""}: {query?:string}) {
  return <form className="discover-search" method="get" action="/discover" role="search"><label className="search-field"><Search size={18} aria-hidden="true"/><span className="sr-only">Search the fragrance catalog</span><input key={query} name="q" type="search" defaultValue={query} placeholder="Search by brand, fragrance or concentration"/></label><Button type="submit">Search catalog</Button>{query.trim() && <Button asChild variant="ghost"><Link href="/discover">Clear search</Link></Button>}</form>;
}
