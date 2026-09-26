"use client";

import { useActionState, useEffect, useState, useTransition } from "react";

import { Field, FormMessage } from "@/components/shared/form-field";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { idleState, type ActionState } from "@/lib/action-state";
import { addToCollection, createCustomFragrance, searchCatalogPage } from "@/lib/server/actions";
import type { FragranceSummary } from "@/types/api";

/**
 * Adds a fragrance to the collection, either from the shared catalog or as a
 * new private custom entry.
 *
 * Both tabs submit through Server Actions, so a failure comes back with field
 * errors and the typed values still in place.
 */
export function AddFragranceDialog({
  open,
  onOpenChange,
  catalog,
  ownedFragranceIds,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  catalog: FragranceSummary[];
  ownedFragranceIds: string[];
}) {
  const [mode, setMode] = useState<"catalog" | "custom">("catalog");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(catalog);
  const [isSearching, startSearch] = useTransition();
  // Close once the save has actually resolved, never optimistically, and from
  // inside the action rather than an effect reacting to the result.
  const [addState, addAction, addPending] = useActionState(
    async (previous: ActionState, formData: FormData) => {
      const result = await addToCollection(previous, formData);
      if (result.status === "success") onOpenChange(false);
      return result;
    },
    idleState,
  );
  const [customState, customAction, customPending] = useActionState(
    createCustomFragrance,
    idleState,
  );

  const owned = new Set(ownedFragranceIds);
  const selectable = results.filter((item) => !owned.has(item.id));

  useEffect(() => {
    const handle = window.setTimeout(() => {
      startSearch(async () => setResults(await searchCatalogPage(query, 0)));
    }, 250);
    return () => window.clearTimeout(handle);
  }, [query]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Add fragrance" eyebrow="Collection">
        {/* Toggle buttons rather than an ARIA tab pattern: a real tablist needs
            arrow-key navigation, and a half-implemented one misleads screen
            reader users about how to move between the panels. */}
        <div className="cluster">
          <Button
            type="button"
            aria-pressed={mode === "catalog"}
            variant={mode === "catalog" ? "primary" : "secondary"}
            size="sm"
            onClick={() => setMode("catalog")}
          >
            From catalog
          </Button>
          <Button
            type="button"
            aria-pressed={mode === "custom"}
            variant={mode === "custom" ? "primary" : "secondary"}
            size="sm"
            onClick={() => setMode("custom")}
          >
            Create custom
          </Button>
        </div>

        {mode === "catalog" ? (
          <form className="form-grid" action={addAction} noValidate>
            <FormMessage state={addState} />
            <div className="field field--full"><label htmlFor="catalog-search">Search the catalog</label><Input id="catalog-search" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Brand or fragrance" /><small>{isSearching ? "Searching…" : `${selectable.length} results`}</small></div>
            <div className="field field--full">
              <Field name="fragrance_id" label="Catalog fragrance" state={addState}>
                {(props) => (
                  <select className="select" {...props}>
                    <option value="">Choose a fragrance</option>
                    {selectable.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.brand.name} — {item.name}
                        {item.is_custom ? " (custom)" : ""}
                      </option>
                    ))}
                  </select>
                )}
              </Field>
            </div>
            <Field name="ownership_type" label="Ownership" state={addState} fallbackValue="bottle">
              {(props) => (
                <select className="select" {...props}>
                  <option value="bottle">Bottle</option>
                  <option value="decant">Decant</option>
                  <option value="sample">Sample</option>
                </select>
              )}
            </Field>
            <Field name="status" label="Status" state={addState} fallbackValue="owned">
              {(props) => (
                <select className="select" {...props}>
                  <option value="owned">Owned</option>
                  <option value="wishlist">Wishlist</option>
                </select>
              )}
            </Field>
            <Field name="bottle_size_ml" label="Bottle size (ml)" state={addState}>
              {(props) => <Input type="number" min="0" step="0.01" {...props} />}
            </Field>
            <Field name="remaining_ml" label="Remaining (ml)" state={addState}>
              {(props) => <Input type="number" min="0" step="0.01" {...props} />}
            </Field>
            <Field
              name="purchase_price"
              label="Purchase price"
              state={addState}
              hint="Optional, e.g. 129.50"
            >
              {(props) => <Input type="text" inputMode="decimal" {...props} />}
            </Field>
            <Field name="purchase_date" label="Purchase date" state={addState}>
              {(props) => <Input type="date" {...props} />}
            </Field>
            <Field name="user_rating" label="Your rating (1–5)" state={addState}>
              {(props) => <Input type="number" min="1" max="5" step="1" {...props} />}
            </Field>
            <div className="field--full cluster">
              <Button type="submit" disabled={addPending}>
                {addPending ? "Adding…" : "Add to collection"}
              </Button>
              <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() =>
                  startSearch(async () => {
                    const more = await searchCatalogPage(query, results.length);
                    setResults((current) => [...current, ...more]);
                  })
                }
              >
                Load more
              </Button>
            </div>
          </form>
        ) : (
          <form className="form-grid" action={customAction} noValidate>
            <FormMessage state={customState} />
            <p className="field--full data-note">
              A custom fragrance is private to your account. Brand, name and concentration are
              required; anything else you leave out simply will not appear in insight breakdowns.
            </p>
            <Field name="brand_name" label="Brand" state={customState}>
              {(props) => <Input type="text" {...props} />}
            </Field>
            <Field name="name" label="Fragrance name" state={customState}>
              {(props) => <Input type="text" {...props} />}
            </Field>
            <Field
              name="concentration"
              label="Concentration"
              state={customState}
              hint="For example eau_de_parfum"
            >
              {(props) => <Input type="text" {...props} />}
            </Field>
            <Field name="release_year" label="Release year" state={customState}>
              {(props) => <Input type="number" min="1700" max="2100" step="1" {...props} />}
            </Field>
            <Field name="projection_level" label="Projection" state={customState}>
              {(props) => (
                <select className="select" {...props}>
                  <option value="">Not sure</option>
                  <option value="intimate">Intimate</option>
                  <option value="moderate">Moderate</option>
                  <option value="strong">Strong</option>
                </select>
              )}
            </Field>
            <div className="field field--full">
              <Field name="description" label="Description" state={customState}>
                {(props) => <textarea className="textarea" rows={3} {...props} />}
              </Field>
            </div>
            <div className="field--full cluster">
              <Button type="submit" disabled={customPending}>
                {customPending ? "Saving…" : "Create fragrance"}
              </Button>
              <Button type="button" variant="ghost" onClick={() => setMode("catalog")}>
                Back to catalog
              </Button>
            </div>
            {customState.status === "success" ? (
              <p className="field--full data-note">
                Saved. Switch to “From catalog” to add it to your collection.
              </p>
            ) : null}
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
