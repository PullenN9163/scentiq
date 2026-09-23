"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Pencil, PlusCircle, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { collection, getDemoFragranceById, wearHistory } from "@/lib/demo";

const editSchema = z.object({
  remaining: z.coerce.number().min(0, "Remaining amount cannot be negative"),
  rating: z.coerce.number().min(1, "Rating must be at least 1").max(5, "Rating cannot exceed 5"),
});
type EditValues = z.infer<typeof editSchema>;
type EditInput = z.input<typeof editSchema>;

export function FragranceDetail({ fragranceId }: { fragranceId: string }) {
  const fragrance = getDemoFragranceById(fragranceId)!;
  const owned = collection.find((item) => item.fragranceId === fragranceId);
  const [editOpen, setEditOpen] = useState(false);
  const [logged, setLogged] = useState(false);
  const [ownership, setOwnership] = useState({ remaining: owned?.remainingMl ?? 0, rating: owned?.rating ?? 4 });
  const { register, handleSubmit, formState: { errors }, reset } = useForm<EditInput, unknown, EditValues>({ resolver: zodResolver(editSchema), defaultValues: ownership });
  const save = (values: EditValues) => { setOwnership(values); setEditOpen(false); };
  const openEdit = () => { reset(ownership); setEditOpen(true); };

  return (
    <section className="page detail-page">
      <Link href="/collection" className="back-link">← Back to collection</Link>
      <div className="detail-hero">
        <div className="detail-art" style={{ "--scent-tone": fragrance.tone } as React.CSSProperties}><span>{fragrance.brand}</span><strong>{fragrance.name}</strong></div>
        <div>
          <p className="eyebrow">{fragrance.brand}</p><h1 className="serif">{fragrance.name}</h1><p className="detail-description">{fragrance.description}</p>
          <div className="cluster">{fragrance.accords.map((accord) => <Badge key={accord}>{accord}</Badge>)}</div>
          <dl className="detail-facts"><div><dt>Longevity</dt><dd>{fragrance.longevity}</dd></div><div><dt>Projection</dt><dd>{fragrance.projection}</dd></div><div><dt>Best seasons</dt><dd>{fragrance.seasons.join(", ")}</dd></div><div><dt>Occasions</dt><dd>{fragrance.occasions.join(", ")}</dd></div></dl>
          <div className="cluster"><Button onClick={openEdit}><Pencil size={16} />Edit</Button><Button variant="secondary" onClick={() => setLogged(true)}><PlusCircle size={16} />{logged ? "Wear logged" : "Log wear"}</Button><Button asChild variant="ghost"><Link href={`/layering?a=${fragrance.id}`}><Sparkles size={16} />Layer it</Link></Button></div>
        </div>
      </div>
      <div className="grid grid-2 detail-sections">
        <Card><CardContent><h2 className="serif">Notes</h2>{["Top", "Middle", "Base"].map((layer) => <div className="note-row" key={layer}><strong>{layer}</strong><span>{fragrance.notes.filter((item) => item.layer === layer).map((item) => item.name).join(", ")}</span></div>)}</CardContent></Card>
        <Card><CardContent><h2 className="serif">Ownership</h2>{owned ? <dl className="note-row"><div><strong>{owned.ownershipType}</strong><span>{ownership.remaining}ml remaining</span></div><div><strong>Rating</strong><span>{ownership.rating.toFixed(1)} / 5</span></div></dl> : <p>Not currently owned.</p>}<h3>Recent wears</h3>{wearHistory.filter((wear) => wear.fragranceId === fragranceId).slice(0, 3).map((wear) => <p key={wear.id}>{wear.date} · {wear.occasion} · {wear.sprays} sprays</p>)}</CardContent></Card>
      </div>
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent title={`Edit ${fragrance.name}`}>
          <form className="form-grid" noValidate onSubmit={handleSubmit(save)}>
            <div className="field"><Label htmlFor="edit-remaining">Remaining (ml)</Label><Input id="edit-remaining" type="number" aria-invalid={Boolean(errors.remaining)} aria-describedby={errors.remaining ? "edit-remaining-error" : undefined} {...register("remaining")} />{errors.remaining && <p id="edit-remaining-error" className="field-error">{errors.remaining.message}</p>}</div>
            <div className="field"><Label htmlFor="edit-rating">Personal rating</Label><Input id="edit-rating" type="number" step="0.1" aria-invalid={Boolean(errors.rating)} aria-describedby={errors.rating ? "edit-rating-error" : undefined} {...register("rating")} />{errors.rating && <p id="edit-rating-error" className="field-error">{errors.rating.message}</p>}</div>
            <div className="field--full cluster"><Button type="submit">Save demo changes</Button><Button type="button" variant="ghost" onClick={() => setEditOpen(false)}>Cancel</Button></div>
          </form>
        </DialogContent>
      </Dialog>
    </section>
  );
}
