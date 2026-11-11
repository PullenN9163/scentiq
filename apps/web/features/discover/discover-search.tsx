import { Search } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export function DiscoverSearch({query="", onChange, onSubmit, onClear}: {query?:string; onChange?:(value:string)=>void; onSubmit?:()=>void; onClear?:()=>void}) {
  return <form className="discover-search" onSubmit={(event)=>{event.preventDefault(); onSubmit?.();}} role="search"><label className="search-field"><Search size={18} aria-hidden="true"/><span className="sr-only">Search the fragrance catalog</span><input name="q" type="search" value={query} maxLength={120} onChange={(event)=>onChange?.(event.target.value)} placeholder="Search by brand, fragrance or concentration"/></label><Button type="submit">Search catalog</Button>{query.trim() && <Button asChild variant="ghost"><Link href="/discover" onClick={event=>{event.preventDefault();onClear?.();}}>Clear search</Link></Button>}</form>;
}
