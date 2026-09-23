"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, Search, X } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { collection, fragrances, getDemoFragranceById } from "@/lib/demo";

const addSchema = z.object({ fragranceId: z.string().min(1, "Choose a fragrance"), ownershipType: z.string(), size: z.coerce.number().positive(), remaining: z.coerce.number().min(0), price: z.coerce.number().min(0), purchaseDate: z.string(), rating: z.coerce.number().min(1).max(5) });
type AddValues = z.output<typeof addSchema>;
type AddInput = z.input<typeof addSchema>;

export function CollectionExperience() {
  const [query, setQuery] = useState("");
  const [ownership, setOwnership] = useState("All");
  const [sort, setSort] = useState("rating");
  const [addOpen, setAddOpen] = useState(false);
  const [saved, setSaved] = useState(false);
  const { register, handleSubmit, formState: { errors } } = useForm<AddInput, unknown, AddValues>({ resolver: zodResolver(addSchema), defaultValues: { fragranceId: "", ownershipType: "Bottle", size: 100, remaining: 100, price: 0, purchaseDate: "", rating: 4 } });
  const items = useMemo(() => collection.map((item) => ({ ...item, fragrance: getDemoFragranceById(item.fragranceId)! })).filter((item) => `${item.fragrance.brand} ${item.fragrance.name}`.toLowerCase().includes(query.toLowerCase()) && (ownership === "All" || item.ownershipType === ownership)).sort((a, b) => sort === "name" ? a.fragrance.name.localeCompare(b.fragrance.name) : b.rating - a.rating), [query, ownership, sort]);
  const counts = collection.reduce<Record<string, number>>((result, item) => ({ ...result, [item.ownershipType]: (result[item.ownershipType] ?? 0) + 1 }), {});
  return (
    <section className="page">
      <PageHeader eyebrow="Your wardrobe" title="Collection" description={`${collection.length} owned · ${counts.Bottle} bottles · ${counts.Decant} decants · ${counts.Sample} samples`} action={<Button onClick={() => setAddOpen(true)}><Plus size={17} />Add fragrance</Button>} />
      {saved && <p className="success-note" role="status">Demo fragrance added for this session.</p>}
      <div className="collection-tools"><label className="search-field"><Search size={18} /><span className="sr-only">Search collection</span><input type="search" aria-label="Search collection" placeholder="Search brand or fragrance" value={query} onChange={(event) => setQuery(event.target.value)} /></label><label><span>Ownership</span><select className="select" value={ownership} onChange={(event) => setOwnership(event.target.value)}><option>All</option><option>Bottle</option><option>Decant</option><option>Sample</option></select></label><label><span>Sort</span><select className="select" value={sort} onChange={(event) => setSort(event.target.value)}><option value="rating">Highest rated</option><option value="name">Name</option></select></label></div>
      {items.length ? <div className="fragrance-grid">{items.map((item) => <Card key={item.id} className="fragrance-card" data-testid="fragrance-card"><Link href={`/collection/${item.fragrance.id}`} aria-label={`Open ${item.fragrance.name}`}><div className="fragrance-card__art" style={{ "--scent-tone": item.fragrance.tone } as React.CSSProperties}><span>{item.fragrance.brand}</span></div><CardContent><div className="cluster"><Badge>{item.ownershipType}</Badge><span className="rating">★ {item.rating.toFixed(1)}</span></div><h2 className="serif">{item.fragrance.name}</h2><p>{item.fragrance.brand} · {item.fragrance.concentration}</p><div className="accord-list">{item.fragrance.accords.map((accord) => <span key={accord}>{accord}</span>)}</div><small>{item.remainingMl}ml of {item.sizeMl}ml remaining</small></CardContent></Link></Card>)}</div> : <Card><CardContent className="empty-panel"><h2>No fragrances found</h2><p>Try a broader search or clear the ownership filter.</p><Button variant="secondary" onClick={() => { setQuery(""); setOwnership("All"); }}>Clear filters</Button></CardContent></Card>}
      {addOpen && <div className="modal-backdrop"><div className="modal" role="dialog" aria-modal="true" aria-label="Add fragrance"><div className="modal__header"><div><p className="eyebrow">Collection demo</p><h2 className="serif">Add fragrance</h2></div><button aria-label="Close add fragrance" onClick={() => setAddOpen(false)}><X /></button></div><form className="form-grid" noValidate onSubmit={handleSubmit(() => { setSaved(true); setAddOpen(false); })}><div className="field field--full"><Label htmlFor="catalog-fragrance">Catalog fragrance</Label><select id="catalog-fragrance" className="select" {...register("fragranceId")}><option value="">Choose a fragrance</option>{fragrances.slice(12).map((item) => <option value={item.id} key={item.id}>{item.brand} — {item.name}</option>)}</select>{errors.fragranceId && <p className="field-error">{errors.fragranceId.message}</p>}</div>{[["ownershipType", "Ownership", "select"], ["size", "Bottle size (ml)", "number"], ["remaining", "Remaining (ml)", "number"], ["price", "Purchase price", "number"], ["purchaseDate", "Purchase date", "date"], ["rating", "Personal rating", "number"]].map(([name, label, type]) => <div className="field" key={name}><Label htmlFor={`add-${name}`}>{label}</Label>{type === "select" ? <select id={`add-${name}`} className="select" {...register(name as keyof AddValues)}><option>Bottle</option><option>Decant</option><option>Sample</option></select> : <Input id={`add-${name}`} type={type} step={name === "rating" ? "0.1" : undefined} {...register(name as keyof AddValues)} />}</div>)}<div className="field--full cluster"><Button type="submit">Add to collection</Button><Button type="button" variant="ghost" onClick={() => setAddOpen(false)}>Cancel</Button></div></form></div></div>}
    </section>
  );
}
