"use client";

import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { MoreHorizontal } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useActionState, useId, useRef, useState, useTransition } from "react";
import { toast } from "sonner";

import { Button } from "@/components/atelier/button";
import { Chip } from "@/components/atelier/chip";
import { Field, Select, TextInput } from "@/components/atelier/field";
import { centerOf, playMist } from "@/components/atelier/mist";
import { Sheet } from "@/components/atelier/sheet";
import { idleState, type ActionState } from "@/lib/action-state";
import { addToCollection, addToWishlist, updateCollectionItem } from "@/lib/server/actions";
import type { CollectionItem, CollectionStatus, FragranceDetail } from "@/types/api";

import styles from "./fragrance.module.css";
import { WearLogSheet } from "./wear-log-sheet";

export type Ownership = "owned" | "wishlist" | "retired" | "none";
export type PrimaryAction = "wear" | "own" | "wishlist";
export type SecondaryAction = "layer" | "own";
export type MenuAction = "edit" | "rate" | "finish";

/** Which fragrance a status is, for the action matrix. */
export function ownershipOf(item: Pick<CollectionItem, "status"> | null): Ownership {
  if (!item) return "none";
  if (item.status === "owned") return "owned";
  if (item.status === "wishlist") return "wishlist";
  return "retired";
}

/**
 * The action matrix. Owned: Wear it, Layer it, and edit / rate / mark
 * finished. Wishlist: I own this, Layer it. Not in the collection: Add to
 * wishlist, I own this. Finished or sold: Layer it, with edit and rate.
 * There is no remove action in the API, so none is offered.
 */
export function actionsFor(ownership: Ownership): { primary: PrimaryAction | null; secondary: SecondaryAction; menu: MenuAction[] } {
  switch (ownership) {
    case "owned": return { primary: "wear", secondary: "layer", menu: ["edit", "rate", "finish"] };
    case "wishlist": return { primary: "own", secondary: "layer", menu: [] };
    case "retired": return { primary: null, secondary: "layer", menu: ["edit", "rate"] };
    default: return { primary: "wishlist", secondary: "own", menu: [] };
  }
}



/** The item's current values, so a partial update does not clear other fields. */
function currentValues(item: CollectionItem, overrides: Partial<Record<string, string>> = {}): FormData {
  const form = new FormData();
  form.set("item_id", item.id);
  form.set("ownership_type", item.ownership_type);
  form.set("status", item.status);
  form.set("remaining_ml", item.remaining_ml?.toString() ?? "");
  form.set("purchase_price", item.purchase_price ?? "");
  form.set("user_rating", item.user_rating?.toString() ?? "");
  for (const [key, value] of Object.entries(overrides)) form.set(key, value ?? "");
  return form;
}

function valueOf(state: ActionState, name: string, fallback: string): string {
  return state.values?.[name] ?? fallback;
}

export function FragranceActions({ fragrance, item, compact = false }: { fragrance: FragranceDetail; item: CollectionItem | null; compact?: boolean }) {
  const router = useRouter();
  const id = useId();
  const [status, setStatus] = useState<CollectionStatus | null>(item?.status ?? null);
  const ownership = ownershipOf(status ? { status } : null);
  const { primary, secondary, menu } = actionsFor(ownership);
  const [wearOpen, setWearOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [rateOpen, setRateOpen] = useState(false);
  const [rating, setRating] = useState<number | null>(item?.user_rating ?? null);
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState<(() => void) | null>(null);
  const wearButton = useRef<HTMLButtonElement>(null);


  const [editState, editAction, editPending] = useActionState(async (previous: ActionState, form: FormData) => {
    const result = await updateCollectionItem(previous, form);
    if (result.status === "success") {
      setEditOpen(false);
      setStatus((form.get("status") as CollectionStatus) || status);
      toast.success(result.message ?? "Collection item updated.");
      router.refresh();
    }
    return result;
  }, idleState);

  function run(label: string, task: () => Promise<ActionState | void>, onSuccess: () => void) {
    const attempt = () => startTransition(async () => {
      try {
        const result = await task();
        if (result && result.status === "error") {
          setError(result.message ?? Object.values(result.fieldErrors ?? {})[0] ?? `Could not ${label}. Try again.`);
          setRetry(() => attempt);
          return;
        }
        setError(null);
        setRetry(null);
        onSuccess();
        router.refresh();
      } catch {
        setError(`Could not ${label}. Try again.`);
        setRetry(() => attempt);
      }
    });
    attempt();
  }

  function own() {
    if (item && status === "wishlist") {
      run("move it to your shelf", () => updateCollectionItem(idleState, currentValues(item, { status: "owned" })), () => { setStatus("owned"); toast.success("On your shelf"); });
    } else {
      const form = new FormData();
      form.set("fragrance_id", fragrance.id);
      form.set("status", "owned");
      form.set("ownership_type", "bottle");
      run("add it to your shelf", () => addToCollection(idleState, form), () => { setStatus("owned"); toast.success("Added to your shelf"); });
    }
  }

  function wishlist() {
    const form = new FormData();
    form.set("fragrance_id", fragrance.id);
    run("add it to your wishlist", () => addToWishlist(form), () => { setStatus("wishlist"); toast.success("Added to your wishlist"); });
  }

  function finish() {
    if (!item) return;
    run("mark it finished", () => updateCollectionItem(idleState, currentValues(item, { status: "finished" })), () => { setStatus("finished"); toast.success("Marked finished"); });
  }

  function saveRating() {
    if (!item || rating === null) return;
    run("save your rating", () => updateCollectionItem(idleState, currentValues(item, { user_rating: String(rating), status: status ?? item.status })), () => { setRateOpen(false); toast.success("Rating saved"); });
  }

  const busy = pending || editPending;
  const ownLabel = pending ? "Saving…" : "I own this";
  const layerLink = <Button asChild variant="soft"><Link href={`/layering?a=${fragrance.id}`}>Layer it</Link></Button>;

  return (
    <div className={styles.actions}>
      <div className={styles.actionRow}>
        {primary === "wear" ? <Button ref={wearButton} disabled={busy || !item} onClick={() => setWearOpen(true)}>Wear it</Button> : null}
        {primary === "own" ? <Button disabled={busy} onClick={own}>{ownLabel}</Button> : null}
        {primary === "wishlist" ? <Button disabled={busy} onClick={wishlist}>{pending ? "Adding…" : "Add to wishlist"}</Button> : null}
        {secondary === "layer" ? layerLink : <Button variant="soft" disabled={busy} onClick={own}>{ownLabel}</Button>}
        {!compact && menu.includes("edit") ? <Button variant="outline" disabled={busy} onClick={() => setEditOpen(true)}>Edit</Button> : null}
        {menu.length > 0 ? (
          <DropdownMenu.Root modal={false}>
            <DropdownMenu.Trigger className={styles.more} aria-label="More actions" disabled={busy}>
              <MoreHorizontal aria-hidden="true" />
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content className={styles.menu} align="end" sideOffset={8} collisionPadding={16}>
                {menu.includes("edit") ? <DropdownMenu.Item className={styles.menuItem} onSelect={() => setEditOpen(true)}>Edit</DropdownMenu.Item> : null}
                {menu.includes("rate") ? <DropdownMenu.Item className={styles.menuItem} onSelect={() => setRateOpen(true)}>Rate</DropdownMenu.Item> : null}
                {menu.includes("finish") ? <DropdownMenu.Item className={styles.menuItem} onSelect={finish}>Mark finished</DropdownMenu.Item> : null}
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        ) : null}
      </div>
      {pending ? <p className="sr-only" role="status">Saving…</p> : null}
      {error ? (
        <p className={styles.error} role="alert">
          {error}
          {retry ? <Button size="sm" variant="text" onClick={() => retry()}>Try again</Button> : null}
        </p>
      ) : null}

      {item ? (
        <>
          <WearLogSheet itemId={item.id} fragranceName={fragrance.name} open={wearOpen} onOpenChange={setWearOpen} onLogged={() => { if (wearButton.current) void playMist({ from: centerOf(wearButton.current), color: getComputedStyle(wearButton.current).getPropertyValue("--ac").trim() || "#8a5a3c" }); }} />

          <Sheet
            open={editOpen}
            onOpenChange={setEditOpen}
            title={`Edit ${fragrance.name}`}
            footer={<div className={styles.sheetActions}><Button type="submit" form={`${id}-edit`} disabled={editPending}>{editPending ? "Saving…" : "Save changes"}</Button><Button variant="text" onClick={() => setEditOpen(false)}>Cancel</Button></div>}
          >
            <form id={`${id}-edit`} action={editAction} className={styles.form} noValidate>
              {editState.status === "error" && editState.message ? <p className={styles.error} role="alert">{editState.message}</p> : null}
              <input type="hidden" name="item_id" value={item.id} />
              <Field label="Remaining (ml)" htmlFor={`${id}-remaining`} error={editState.fieldErrors?.remaining_ml}>
                <TextInput id={`${id}-remaining`} name="remaining_ml" type="number" inputMode="decimal" min={0} step={0.01} defaultValue={valueOf(editState, "remaining_ml", item.remaining_ml?.toString() ?? "")} />
              </Field>
              <Field label="Your rating (1 to 5)" htmlFor={`${id}-rating`} error={editState.fieldErrors?.user_rating}>
                <TextInput id={`${id}-rating`} name="user_rating" type="number" min={1} max={5} step={1} defaultValue={valueOf(editState, "user_rating", item.user_rating?.toString() ?? "")} />
              </Field>
              <Field label="Purchase price" htmlFor={`${id}-price`} error={editState.fieldErrors?.purchase_price}>
                <TextInput id={`${id}-price`} name="purchase_price" inputMode="decimal" defaultValue={valueOf(editState, "purchase_price", item.purchase_price ?? "")} />
              </Field>
              <Field label="Format" htmlFor={`${id}-format`} error={editState.fieldErrors?.ownership_type}>
                <Select id={`${id}-format`} name="ownership_type" defaultValue={valueOf(editState, "ownership_type", item.ownership_type)}>
                  <option value="bottle">Bottle</option>
                  <option value="decant">Decant</option>
                  <option value="sample">Sample</option>
                </Select>
              </Field>
              <Field label="Status" htmlFor={`${id}-status`} hint="Finished and sold keep your wear history." error={editState.fieldErrors?.status}>
                <Select id={`${id}-status`} name="status" defaultValue={valueOf(editState, "status", status ?? item.status)}>
                  <option value="owned">Owned</option>
                  <option value="wishlist">Wishlist</option>
                  <option value="finished">Finished</option>
                  <option value="sold">Sold</option>
                </Select>
              </Field>
            </form>
          </Sheet>

          <Sheet
            open={rateOpen}
            onOpenChange={setRateOpen}
            title={`Rate ${fragrance.name}`}
            footer={<div className={styles.sheetActions}><Button disabled={pending || rating === null} onClick={saveRating}>{pending ? "Saving…" : "Save rating"}</Button><Button variant="text" onClick={() => setRateOpen(false)}>Cancel</Button></div>}
          >
            <div className={styles.rating} role="group" aria-label="Your rating out of 5">
              {[1, 2, 3, 4, 5].map((value) => <Chip key={value} variant="choice" pressed={rating === value} onClick={() => setRating(value)}>{value}</Chip>)}
            </div>
          </Sheet>
        </>
      ) : null}
    </div>
  );
}
