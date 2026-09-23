"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { collection, fragrances, getDemoFragranceById } from "@/lib/demo";
import type { CollectionItem, OwnershipType } from "@/types/demo";

const addSchema = z.object({ fragranceId: z.string().min(1, "Choose a fragrance"), ownershipType: z.enum(["Bottle", "Decant", "Sample"]), size: z.coerce.number().positive("Size must be greater than zero"), remaining: z.coerce.number().min(0, "Remaining amount cannot be negative"), price: z.coerce.number().min(0, "Price cannot be negative"), purchaseDate: z.string().min(1, "Purchase date is required"), rating: z.coerce.number().min(1, "Rating must be at least 1").max(5, "Rating cannot exceed 5") }).refine((values) => values.remaining <= values.size, { path: ["remaining"], message: "Remaining amount cannot exceed bottle size" });
type AddValues = z.output<typeof addSchema>;
type AddInput = z.input<typeof addSchema>;

export function CollectionExperience() {
  const [query, setQuery] = useState("");
  const [ownership, setOwnership] = useState("All");
  const [sort, setSort] = useState("rating");
  const [addOpen, setAddOpen] = useState(false);
  const [saved, setSaved] = useState(false);
  const [sessionItems, setSessionItems] = useState<CollectionItem[]>([]);
  const { register, handleSubmit, formState: { errors }, reset } = useForm<AddInput, unknown, AddValues>({ resolver: zodResolver(addSchema), defaultValues: { fragranceId: "", ownershipType: "Bottle", size: 100, remaining: 100, price: 0, purchaseDate: "", rating: 4 } });
  const allItems = useMemo(() => [...collection, ...sessionItems], [sessionItems]);
  const items = useMemo(() => allItems.map((item) => ({ ...item, fragrance: getDemoFragranceById(item.fragranceId)! })).filter((item) => `${item.fragrance.brand} ${item.fragrance.name}`.toLowerCase().includes(query.toLowerCase()) && (ownership === "All" || item.ownershipType === ownership)).sort((a, b) => sort === "name" ? a.fragrance.name.localeCompare(b.fragrance.name) : b.rating - a.rating), [allItems, query, ownership, sort]);
  const counts = allItems.reduce<Record<string, number>>((result, item) => ({ ...result, [item.ownershipType]: (result[item.ownershipType] ?? 0) + 1 }), {});
  const addItem = (values: AddValues) => { setSessionItems((current) => [...current, { id: `session-${values.fragranceId}`, fragranceId: values.fragranceId, ownershipType: values.ownershipType as OwnershipType, sizeMl: values.size, remainingMl: values.remaining, purchasePrice: values.price, purchaseDate: values.purchaseDate, rating: values.rating }]); setSaved(true); setAddOpen(false); reset(); };
  return (
    <section className="page">
      <PageHeader eyebrow="Your wardrobe" title="Collection" description={`${allItems.length} owned · ${counts.Bottle ?? 0} bottles · ${counts.Decant ?? 0} decants · ${counts.Sample ?? 0} samples`} action={<Button onClick={() => setAddOpen(true)}><Plus size={17} />Add fragrance</Button>} />
      {saved && <p className="success-note" role="status">Demo fragrance added for this session.</p>}
      <div className="collection-tools"><label className="search-field"><Search size={18} /><span className="sr-only">Search collection</span><input type="search" aria-label="Search collection" placeholder="Search brand or fragrance" value={query} onChange={(event) => setQuery(event.target.value)} /></label><label><span>Ownership</span><select className="select" value={ownership} onChange={(event) => setOwnership(event.target.value)}><option>All</option><option>Bottle</option><option>Decant</option><option>Sample</option></select></label><label><span>Sort</span><select className="select" value={sort} onChange={(event) => setSort(event.target.value)}><option value="rating">Highest rated</option><option value="name">Name</option></select></label></div>
      {items.length ? <div className="fragrance-grid">{items.map((item) => <Card key={item.id} className="fragrance-card" data-testid="fragrance-card"><Link href={`/collection/${item.fragrance.id}`} aria-label={`Open ${item.fragrance.name}`}><div className="fragrance-card__art" style={{ "--scent-tone": item.fragrance.tone } as React.CSSProperties}><span>{item.fragrance.brand}</span></div><CardContent><div className="cluster"><Badge>{item.ownershipType}</Badge><span className="rating">★ {item.rating.toFixed(1)}</span></div><h2 className="serif">{item.fragrance.name}</h2><p>{item.fragrance.brand} · {item.fragrance.concentration}</p><div className="accord-list">{item.fragrance.accords.map((accord) => <span key={accord}>{accord}</span>)}</div><small>{item.remainingMl}ml of {item.sizeMl}ml remaining</small></CardContent></Link></Card>)}</div> : <Card><CardContent className="empty-panel"><h2>{allItems.length ? "No fragrances found" : "Start your fragrance wardrobe"}</h2><p>{allItems.length ? "Try a broader search or clear the ownership filter." : "Add your first bottle, decant, or sample to unlock recommendations."}</p><Button variant="secondary" onClick={() => allItems.length ? (setQuery(""), setOwnership("All")) : setAddOpen(true)}>{allItems.length ? "Clear filters" : "Add first fragrance"}</Button></CardContent></Card>}
      <Dialog open={addOpen} onOpenChange={setAddOpen}><DialogContent title="Add fragrance" eyebrow="Collection demo"><form className="form-grid" noValidate onSubmit={handleSubmit(addItem)}><div className="field field--full"><Label htmlFor="catalog-fragrance">Catalog fragrance</Label><select id="catalog-fragrance" className="select" aria-invalid={Boolean(errors.fragranceId)} aria-describedby={errors.fragranceId ? "add-fragrance-error" : undefined} {...register("fragranceId")}><option value="">Choose a fragrance</option>{fragrances.slice(12).map((item) => <option value={item.id} key={item.id}>{item.brand} — {item.name}</option>)}</select>{errors.fragranceId && <p id="add-fragrance-error" className="field-error">{errors.fragranceId.message}</p>}</div>{[["ownershipType", "Ownership", "select"], ["size", "Bottle size (ml)", "number"], ["remaining", "Remaining (ml)", "number"], ["price", "Purchase price", "number"], ["purchaseDate", "Purchase date", "date"], ["rating", "Personal rating", "number"]].map(([name, label, type]) => { const error = errors[name as keyof AddInput]; const errorId = `add-${name}-error`; return <div className="field" key={name}><Label htmlFor={`add-${name}`}>{label}</Label>{type === "select" ? <select id={`add-${name}`} className="select" aria-invalid={Boolean(error)} aria-describedby={error ? errorId : undefined} {...register(name as keyof AddInput)}><option>Bottle</option><option>Decant</option><option>Sample</option></select> : <Input id={`add-${name}`} type={type} step={name === "rating" ? "0.1" : undefined} aria-invalid={Boolean(error)} aria-describedby={error ? errorId : undefined} {...register(name as keyof AddInput)} />}{error && <p id={errorId} className="field-error">{error.message}</p>}</div>; })}<div className="field--full cluster"><Button type="submit">Add to collection</Button><Button type="button" variant="ghost" onClick={() => setAddOpen(false)}>Cancel</Button></div></form></DialogContent></Dialog>
    </section>
  );
}
