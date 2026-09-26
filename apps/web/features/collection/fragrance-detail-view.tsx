"use client";

import { Pencil, PlusCircle, Sparkles } from "lucide-react";
import Link from "next/link";
import { useActionState, useState } from "react";

import { Field, FormMessage } from "@/components/shared/form-field";
import { CatalogImage } from "@/components/catalog-image";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { idleState, type ActionState } from "@/lib/action-state";
import { logWear, updateCollectionItem } from "@/lib/server/actions";
import type { CollectionItem, FragranceDetail, WearLogEntry } from "@/types/api";

const STAGES: { key: "top" | "middle" | "base" | "general"; label: string }[] = [
  { key: "top", label: "Top" },
  { key: "middle", label: "Middle" },
  { key: "base", label: "Base" },
  { key: "general", label: "Notes" },
];

function formatWhen(value: string): string {
  // Fixed locale and UTC so server and client markup agree.
  return new Date(value).toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  });
}

/** A datetime-local value for "now", which the input requires unzoned. */
function nowForInput(): string {
  return new Date().toISOString().slice(0, 16);
}

export function FragranceDetailView({
  fragrance,
  ownedItem,
  wears,
}: {
  fragrance: FragranceDetail;
  ownedItem: CollectionItem | null;
  wears: WearLogEntry[];
}) {
  const [editOpen, setEditOpen] = useState(false);
  const [logOpen, setLogOpen] = useState(false);
  // Closing happens inside the action, after the save resolves, rather than in
  // an effect reacting to the result. An effect would re-render to close.
  const [editState, editAction, editPending] = useActionState(
    async (previous: ActionState, formData: FormData) => {
      const result = await updateCollectionItem(previous, formData);
      if (result.status === "success") setEditOpen(false);
      return result;
    },
    idleState,
  );
  const [wearState, wearAction, wearPending] = useActionState(
    async (previous: ActionState, formData: FormData) => {
      const result = await logWear(previous, formData);
      if (result.status === "success") setLogOpen(false);
      return result;
    },
    idleState,
  );

  const occasions = fragrance.occasions.map((entry) => entry.occasion).join(", ");
  const dayVotes = fragrance.community?.day_votes ?? null;
  const nightVotes = fragrance.community?.night_votes ?? null;
  const daypartTotal = (dayVotes ?? 0) + (nightVotes ?? 0);

  return (
    <section className="page detail-page">
      <Link href="/collection" className="back-link">
        ← Back to collection
      </Link>

      <div className="detail-hero">
        <CatalogImage className="detail-art" id={fragrance.id} name={fragrance.name} brand={fragrance.brand.name} imageUrl={fragrance.image_url} />
        <div>
          <p className="eyebrow">{fragrance.brand.name}</p>
          <h1 className="serif">{fragrance.name}</h1>
          <p className="detail-description">
            {fragrance.description ?? "No description recorded for this fragrance."}
          </p>
          <div className="cluster">
            {fragrance.is_custom ? <Badge>Custom</Badge> : null}
            {fragrance.accords.map((accord) => (
              <Badge key={accord.id}>{accord.name}</Badge>
            ))}
          </div>
          <dl className="detail-facts">
            <div><dt>Gender</dt><dd>{fragrance.gender ?? "Not recorded"}</dd></div>
            <div><dt>Family</dt><dd>{fragrance.olfactory_family ?? "Not recorded"}</dd></div>
            <div><dt>Product line</dt><dd>{fragrance.product_line ?? "Not recorded"}</dd></div>
            <div><dt>Brand country</dt><dd>{fragrance.brand.country ?? "Not recorded"}</dd></div>
            <div><dt>Perfumers</dt><dd>{fragrance.perfumers.map((item) => item.name).join(", ") || "Not recorded"}</dd></div>
            <div><dt>Community rating</dt><dd>{fragrance.rating_average === null ? "Not enough community data" : `${fragrance.rating_average.toFixed(2)} / 5 (${fragrance.rating_count ?? "vote count unknown"})`}</dd></div>
            <div>
              <dt>Longevity</dt>
              <dd>
                {fragrance.longevity_score === null
                  ? "Not recorded"
                  : `${fragrance.longevity_score} / 10`}
              </dd>
            </div>
            <div>
              <dt>Projection</dt>
              <dd>{fragrance.projection_level ?? "Not recorded"}</dd>
            </div>
            <div>
              <dt>Best seasons</dt>
              <dd>
                {fragrance.seasons.length
                  ? fragrance.seasons.map((entry) => entry.season).join(", ")
                  : "Not recorded"}
              </dd>
            </div>
            <div>
              <dt>Occasions</dt>
              <dd>{occasions || "Not recorded"}</dd>
            </div>
          </dl>
          <div className="cluster">
            {ownedItem ? (
              <>
                <Button onClick={() => setEditOpen(true)}>
                  <Pencil size={16} />
                  Edit
                </Button>
                <Button variant="secondary" onClick={() => setLogOpen(true)}>
                  <PlusCircle size={16} />
                  Log wear
                </Button>
              </>
            ) : null}
            <Button asChild variant="ghost">
              <Link href={`/layering?a=${fragrance.id}`}>
                <Sparkles size={16} />
                Layer it
              </Link>
            </Button>
          </div>
          {editState.status === "success" || wearState.status === "success" ? (
            <p className="success-note" role="status">
              {editState.status === "success" ? editState.message : wearState.message}
            </p>
          ) : null}
        </div>
      </div>

      <div className="grid grid-2 detail-sections">
        <Card>
          <CardContent>
            <h2 className="serif">Notes</h2>
            {fragrance.notes.length === 0 ? (
              <p className="muted">
                No notes recorded.
                {fragrance.is_custom ? " Custom entries start without note data." : ""}
              </p>
            ) : (
              STAGES.map(({ key, label }) => {
                const names = fragrance.notes
                  .filter((note) => note.stage === key)
                  .map((note) => `${note.name}${note.weight === null ? "" : ` (${Math.round(note.weight * 100)}%)`}`)
                  .join(", ");
                return (
                  <div className="note-row" key={key}>
                    <strong>{label}</strong>
                    <span>{names || "—"}</span>
                  </div>
                );
              })
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <h2 className="serif">Ownership</h2>
            {ownedItem ? (
              <dl className="note-row">
                <div>
                  <strong>{ownedItem.ownership_type}</strong>
                  <span>
                    {ownedItem.remaining_ml === null
                      ? "No volume recorded"
                      : `${ownedItem.remaining_ml}ml remaining`}
                  </span>
                </div>
                <div>
                  <strong>Rating</strong>
                  <span>
                    {ownedItem.user_rating === null ? "Not rated" : `${ownedItem.user_rating} / 5`}
                  </span>
                </div>
                <div>
                  <strong>Status</strong>
                  <span>{ownedItem.status}</span>
                </div>
                <div>
                  <strong>Paid</strong>
                  <span>{ownedItem.purchase_price ?? "Not recorded"}</span>
                </div>
              </dl>
            ) : (
              <p className="muted">Not currently in your collection.</p>
            )}

            <h3>Recent wears</h3>
            {wears.length === 0 ? (
              <p className="muted">No wears logged yet.</p>
            ) : (
              wears.slice(0, 5).map((wear) => (
                <p key={wear.id}>
                  {formatWhen(wear.worn_at)}
                  {wear.occasion ? ` · ${wear.occasion}` : ""}
                  {wear.sprays === null ? "" : ` · ${wear.sprays} sprays`}
                </p>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-2 detail-sections">
        <Card>
          <CardContent>
            <h2 className="serif">Community</h2>
            {fragrance.community ? (
              <dl className="detail-facts">
                <div><dt>Longevity</dt><dd>{fragrance.community.longevity_average === null ? "Not enough community data" : `${fragrance.community.longevity_average.toFixed(2)} / 5 (${fragrance.community.longevity_votes ?? "vote count unknown"})`}</dd></div>
                <div><dt>Sillage</dt><dd>{fragrance.community.sillage_average === null ? "Not enough community data" : `${fragrance.community.sillage_average.toFixed(2)} / 4 (${fragrance.community.sillage_votes ?? "vote count unknown"})`}</dd></div>
                <div><dt>Price value</dt><dd>{fragrance.community.price_value_average === null ? "Not enough community data" : `${fragrance.community.price_value_average.toFixed(2)} / 5 (${fragrance.community.price_value_votes ?? "vote count unknown"})`}</dd></div>
              </dl>
            ) : <p>Not enough community data</p>}
            <h3>Season strength</h3>
            {fragrance.seasons.length ? fragrance.seasons.map((entry) => <div key={entry.season}><span>{entry.season}</span><Progress value={entry.weight * 100} label={`${entry.season} strength`} /></div>) : <p className="muted">Not enough community data</p>}
            <h3>Day / night</h3>
            {daypartTotal > 0 ? <><div><span>Day</span><Progress value={((dayVotes ?? 0) / daypartTotal) * 100} label="Day votes" /></div><div><span>Night</span><Progress value={((nightVotes ?? 0) / daypartTotal) * 100} label="Night votes" /></div></> : <p className="muted">Not enough community data</p>}
          </CardContent>
        </Card>
        <Card><CardContent><h2 className="serif">Similar fragrances</h2>{fragrance.similar.length ? fragrance.similar.map((item) => <p key={item.id}><Link href={`/collection/${item.id}`}>{item.brand.name} · {item.name}</Link></p>) : <p className="muted">Not enough community data</p>}</CardContent></Card>
      </div>
      <p className="data-note">Sources: {fragrance.sources.length ? fragrance.sources.map((source) => source.url ? <a key={`${source.source}-${source.url}`} href={source.url} rel="noreferrer" target="_blank">{source.source}</a> : <span key={source.source}>{source.source}</span>).reduce<React.ReactNode[]>((items, item, index) => [...items, index ? ", " : "", item], []) : "Private custom entry"}</p>

      {ownedItem ? (
        <>
          <Dialog open={editOpen} onOpenChange={setEditOpen}>
            <DialogContent title={`Edit ${fragrance.name}`}>
              <form className="form-grid" action={editAction} noValidate>
                <FormMessage state={editState} />
                <input type="hidden" name="item_id" value={ownedItem.id} />
                <Field
                  name="remaining_ml"
                  label="Remaining (ml)"
                  state={editState}
                  fallbackValue={ownedItem.remaining_ml?.toString() ?? ""}
                >
                  {(props) => <Input type="number" min="0" step="0.01" {...props} />}
                </Field>
                <Field
                  name="user_rating"
                  label="Your rating (1–5)"
                  state={editState}
                  fallbackValue={ownedItem.user_rating?.toString() ?? ""}
                >
                  {(props) => <Input type="number" min="1" max="5" step="1" {...props} />}
                </Field>
                <Field
                  name="purchase_price"
                  label="Purchase price"
                  state={editState}
                  fallbackValue={ownedItem.purchase_price ?? ""}
                >
                  {(props) => <Input type="text" inputMode="decimal" {...props} />}
                </Field>
                <Field
                  name="ownership_type"
                  label="Ownership"
                  state={editState}
                  fallbackValue={ownedItem.ownership_type}
                >
                  {(props) => (
                    <select className="select" {...props}>
                      <option value="bottle">Bottle</option>
                      <option value="decant">Decant</option>
                      <option value="sample">Sample</option>
                    </select>
                  )}
                </Field>
                <div className="field field--full">
                  <Field
                    name="status"
                    label="Status"
                    state={editState}
                    fallbackValue={ownedItem.status}
                    hint="Finished and sold keep your wear history instead of deleting it."
                  >
                    {(props) => (
                      <select className="select" {...props}>
                        <option value="owned">Owned</option>
                        <option value="wishlist">Wishlist</option>
                        <option value="finished">Finished</option>
                        <option value="sold">Sold</option>
                      </select>
                    )}
                  </Field>
                </div>
                <div className="field--full cluster">
                  <Button type="submit" disabled={editPending}>
                    {editPending ? "Saving…" : "Save changes"}
                  </Button>
                  <Button type="button" variant="ghost" onClick={() => setEditOpen(false)}>
                    Cancel
                  </Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>

          <Dialog open={logOpen} onOpenChange={setLogOpen}>
            <DialogContent title={`Log a wear of ${fragrance.name}`}>
              <form className="form-grid" action={wearAction} noValidate>
                <FormMessage state={wearState} />
                <input type="hidden" name="collection_item_id" value={ownedItem.id} />
                <Field
                  name="worn_at"
                  label="When"
                  state={wearState}
                  fallbackValue={nowForInput()}
                >
                  {(props) => <Input type="datetime-local" {...props} />}
                </Field>
                <Field name="sprays" label="Sprays" state={wearState}>
                  {(props) => <Input type="number" min="1" max="30" step="1" {...props} />}
                </Field>
                <Field name="occasion" label="Occasion" state={wearState}>
                  {(props) => (
                    <select className="select" {...props}>
                      <option value="">Not specified</option>
                      <option value="work">Work</option>
                      <option value="casual">Casual</option>
                      <option value="date">Date</option>
                      <option value="dinner">Dinner</option>
                      <option value="party">Party</option>
                      <option value="formal">Formal</option>
                      <option value="gym">Gym</option>
                      <option value="travel">Travel</option>
                      <option value="other">Other</option>
                    </select>
                  )}
                </Field>
                <Field name="setting" label="Setting" state={wearState}>
                  {(props) => <Input type="text" maxLength={40} {...props} />}
                </Field>
                <div className="field field--full">
                  <Field name="notes" label="Notes" state={wearState}>
                    {(props) => <textarea className="textarea" rows={3} {...props} />}
                  </Field>
                </div>
                <div className="field--full cluster">
                  <Button type="submit" disabled={wearPending}>
                    {wearPending ? "Saving…" : "Log wear"}
                  </Button>
                  <Button type="button" variant="ghost" onClick={() => setLogOpen(false)}>
                    Cancel
                  </Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        </>
      ) : null}
    </section>
  );
}
