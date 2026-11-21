"use client";

import { useId, useState } from "react";

import { AtelierEmpty } from "@/components/atelier/states";
import { Button } from "@/components/atelier/button";
import { Field, TextArea, TextInput } from "@/components/atelier/field";
import { Sheet } from "@/components/atelier/sheet";
import type { SavedLayeringStack } from "@/types/layering";

import { BlendVial } from "./blend-vial";
import styles from "./blend.module.css";

/** Name and note for a blend, with the offer to open an identical saved one. */
export function SaveSheet({
  open,
  onOpenChange,
  title,
  submitLabel,
  suggestedName,
  existing,
  pending,
  error,
  onSubmit,
  onOpenExisting,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  submitLabel: string;
  suggestedName: string;
  existing: SavedLayeringStack | null;
  pending: boolean;
  error: string | null;
  onSubmit: (name: string, notes: string) => void;
  onOpenExisting: (id: string) => void;
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title={title} theme="dark">
      {open ? (
        <SaveForm key={suggestedName} submitLabel={submitLabel} suggestedName={suggestedName} existing={existing} pending={pending} error={error} onSubmit={onSubmit} onOpenExisting={onOpenExisting} />
      ) : null}
    </Sheet>
  );
}

function SaveForm({
  submitLabel,
  suggestedName,
  existing,
  pending,
  error,
  onSubmit,
  onOpenExisting,
}: Omit<Parameters<typeof SaveSheet>[0], "open" | "onOpenChange" | "title">) {
  const id = useId();
  const [name, setName] = useState(suggestedName);
  const [notes, setNotes] = useState("");
  if (existing) {
    return (
      <div className={styles.sheetBody}>
        <p className="at-body">You already saved this blend as “{existing.name}”.</p>
        <div className={styles.sheetActions}>
          <Button onClick={() => onOpenExisting(existing.id)}>Open it</Button>
          <Button variant="text" onClick={() => onSubmit(name.trim(), notes.trim())}>Save as a new blend</Button>
        </div>
      </div>
    );
  }
  return (
    <form
      className={styles.sheetBody}
      onSubmit={(event) => {
        event.preventDefault();
        if (name.trim()) onSubmit(name.trim(), notes.trim());
      }}
    >
      <Field label="Name" htmlFor={`${id}-name`}>
        <TextInput id={`${id}-name`} value={name} maxLength={120} required onChange={(event) => setName(event.target.value)} />
      </Field>
      <Field label="Note (optional)" htmlFor={`${id}-notes`}>
        <TextArea id={`${id}-notes`} value={notes} maxLength={2000} rows={3} onChange={(event) => setNotes(event.target.value)} />
      </Field>
      {error ? <p className="at-error" role="alert">{error}</p> : null}
      <div className={styles.sheetActions}>
        <Button type="submit" disabled={pending || !name.trim()}>{pending ? "Saving…" : submitLabel}</Button>
      </div>
    </form>
  );
}

/** After a wear: an optional one-to-five rating. */
export function RatingSheet({ open, onOpenChange, pending, onRate }: { open: boolean; onOpenChange: (open: boolean) => void; pending: boolean; onRate: (rating: number) => void }) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="How did it wear?" description="Optional. You can rate it later from the vault." theme="dark">
      <div className={styles.sheetBody}>
        <div className={styles.ratings} role="group" aria-label="Rating">
          {[1, 2, 3, 4, 5].map((rating) => (
            <button key={rating} type="button" className={styles.rating} aria-label={`Rate ${rating} of 5`} disabled={pending} onClick={() => onRate(rating)}>{rating}</button>
          ))}
        </div>
        <div className={styles.sheetActions}>
          <Button variant="text" onClick={() => onOpenChange(false)}>Skip</Button>
        </div>
      </div>
    </Sheet>
  );
}

/** The cabinet: saved blends as vials. Opening one loads it in the flask. */
export function VaultSheet({ open, onOpenChange, saved }: { open: boolean; onOpenChange: (open: boolean) => void; saved: SavedLayeringStack[] }) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Blends" theme="dark">
      {saved.length === 0 ? (
        <AtelierEmpty title="Your cabinet is empty" action={<Button onClick={() => onOpenChange(false)}>Make your first blend</Button>}>
          Save a blend from the flask and it waits here.
        </AtelierEmpty>
      ) : (
        <ul className={styles.vault} aria-label="Saved blends">
          {saved.map((stack) => <li key={stack.id}><BlendVial stack={stack} onOpen={() => onOpenChange(false)} /></li>)}
        </ul>
      )}
    </Sheet>
  );
}
