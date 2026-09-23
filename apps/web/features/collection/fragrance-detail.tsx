"use client";

import { Pencil, PlusCircle, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { collection, getDemoFragranceById, wearHistory } from "@/lib/demo";

export function FragranceDetail({ fragranceId }: { fragranceId: string }) {
  const fragrance = getDemoFragranceById(fragranceId)!;
  const owned = collection.find((item) => item.fragranceId === fragranceId);
  const [editOpen, setEditOpen] = useState(false);
  const [logged, setLogged] = useState(false);
  return <section className="page detail-page"><Link href="/collection" className="back-link">← Back to collection</Link><div className="detail-hero"><div className="detail-art" style={{ "--scent-tone": fragrance.tone } as React.CSSProperties}><span>{fragrance.brand}</span><strong>{fragrance.name}</strong></div><div><p className="eyebrow">{fragrance.brand}</p><h1 className="serif">{fragrance.name}</h1><p className="detail-description">{fragrance.description}</p><div className="cluster">{fragrance.accords.map((accord) => <Badge key={accord}>{accord}</Badge>)}</div><dl className="detail-facts"><div><dt>Longevity</dt><dd>{fragrance.longevity}</dd></div><div><dt>Projection</dt><dd>{fragrance.projection}</dd></div><div><dt>Best seasons</dt><dd>{fragrance.seasons.join(", ")}</dd></div><div><dt>Occasions</dt><dd>{fragrance.occasions.join(", ")}</dd></div></dl><div className="cluster"><Button onClick={() => setEditOpen(true)}><Pencil size={16} />Edit</Button><Button variant="secondary" onClick={() => setLogged(true)}><PlusCircle size={16} />{logged ? "Wear logged" : "Log wear"}</Button><Button asChild variant="ghost"><Link href={`/layering?a=${fragrance.id}`}><Sparkles size={16} />Layer it</Link></Button></div></div></div><div className="grid grid-2 detail-sections"><Card><CardContent><h2 className="serif">Notes</h2>{["Top", "Middle", "Base"].map((layer) => <div className="note-row" key={layer}><strong>{layer}</strong><span>{fragrance.notes.filter((item) => item.layer === layer).map((item) => item.name).join(", ")}</span></div>)}</CardContent></Card><Card><CardContent><h2 className="serif">Ownership</h2>{owned ? <dl className="note-row"><div><strong>{owned.ownershipType}</strong><span>{owned.remainingMl}ml remaining</span></div><div><strong>Rating</strong><span>{owned.rating.toFixed(1)} / 5</span></div></dl> : <p>Not currently owned.</p>}<h3>Recent wears</h3>{wearHistory.filter((wear) => wear.fragranceId === fragranceId).slice(0, 3).map((wear) => <p key={wear.id}>{wear.date} · {wear.occasion} · {wear.sprays} sprays</p>)}</CardContent></Card></div>{editOpen && <div className="modal-backdrop"><div className="modal" role="dialog" aria-modal="true" aria-label={`Edit ${fragrance.name}`}><div className="modal__header"><h2 className="serif">Edit {fragrance.name}</h2><button aria-label="Close edit" onClick={() => setEditOpen(false)}><X /></button></div><div className="form-grid"><div className="field"><Label htmlFor="edit-remaining">Remaining (ml)</Label><Input id="edit-remaining" type="number" defaultValue={owned?.remainingMl ?? 0} /></div><div className="field"><Label htmlFor="edit-rating">Personal rating</Label><Input id="edit-rating" type="number" step="0.1" defaultValue={owned?.rating ?? 4} /></div><div className="field--full cluster"><Button onClick={() => setEditOpen(false)}>Save demo changes</Button><Button variant="ghost" onClick={() => setEditOpen(false)}>Cancel</Button></div></div></div></div>}</section>;
}
