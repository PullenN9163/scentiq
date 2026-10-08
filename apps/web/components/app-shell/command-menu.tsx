"use client";
import { Command } from "cmdk";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Search } from "lucide-react";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { searchOwnCollection } from "@/lib/server/collection-search";

const destinations = [["Today", "/dashboard"], ["My Week", "/week"], ["Collection", "/collection"], ["Layering Lab", "/layering"], ["Discover", "/discover"], ["Insights", "/insights"], ["Ask ScentIQ", "/agent"], ["Settings", "/settings"]];
export function CommandMenu() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<Awaited<ReturnType<typeof searchOwnCollection>>>([]);
  const [failed, setFailed] = useState(false);
  const sequence = useRef(0);
  useEffect(() => {
    const show = () => setOpen(true);
    const keydown = (event: KeyboardEvent) => { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setOpen((value) => !value); } };
    window.addEventListener("keydown", keydown);
    window.addEventListener("scentiq:command", show);
    return () => { window.removeEventListener("keydown", keydown); window.removeEventListener("scentiq:command", show); };
  }, []);
  useEffect(() => {
    if (!open) return;
    const current = ++sequence.current;
    let active = true;
    const timer = setTimeout(() => { void searchOwnCollection(query).then((result) => { if (active && sequence.current === current) { setItems(result); setFailed(false); } }).catch(() => { if (active && sequence.current === current) { setItems([]); setFailed(true); } }); }, 180);
    return () => { clearTimeout(timer); active = false; };
  }, [query, open]);
  const go = (href: string) => { setOpen(false); router.push(href); };
  return <><button type="button" className="command-launch" onClick={() => setOpen(true)}><Search size={16} /><span>Search & navigate</span><kbd>Ctrl / ⌘ K</kbd></button><Dialog open={open} onOpenChange={setOpen}><DialogContent title="Search ScentIQ"><Command><Command.Input value={query} onValueChange={setQuery} placeholder="Find a fragrance or destination…" aria-label="Search ScentIQ" /><Command.List><Command.Empty>No matches.</Command.Empty><Command.Group heading="Go to">{destinations.map(([label, href]) => <Command.Item key={href} onSelect={() => go(href)}>{label}</Command.Item>)}</Command.Group><Command.Group heading="Your collection">{items.map((item) => <Command.Item key={item.id} value={`${item.name} ${item.brand}`} onSelect={() => go(`/collection/${item.id}`)}>{item.name}<small>{item.brand}</small></Command.Item>)}</Command.Group></Command.List></Command>{failed && <p role="status" className="muted">Collection search is temporarily unavailable.</p>}</DialogContent></Dialog></>;
}
