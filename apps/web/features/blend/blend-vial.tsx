"use client";

import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { MoreHorizontal } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState, useTransition } from "react";
import { toast } from "sonner";

import { Button } from "@/components/atelier/button";
import { Field, TextInput } from "@/components/atelier/field";
import { Sheet } from "@/components/atelier/sheet";
import { Vial } from "@/components/atelier/vial";
import { accordFor } from "@/lib/accord";
import { cn } from "@/lib/utils";
import { deleteLayerStack, getLayerStackHistory, logLayerStackWear, renameLayerStack } from "@/lib/server/layering-actions";
import type { LayeringStackWear, SavedLayeringStack } from "@/types/layering";

import styles from "./blend-vial.module.css";

/** The fragrances of a saved blend, in application order. */
export function stackMembers(stack: SavedLayeringStack) {
  return [...stack.suggestion.items].sort((a, b) => a.application_order - b.application_order);
}

/** "A + B · worn 3×" */
export function blendCaption(stack: SavedLayeringStack): string {
  const names = stackMembers(stack).map((item) => item.fragrance.name).join(" + ");
  return stack.wear_count > 0 ? `${names} · worn ${stack.wear_count}×` : names;
}

/** "Mar 3, 2026", for a wear or the last time a blend was worn. */
export function formatWearDate(value: string): string {
  return new Date(value).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

/**
 * A saved blend as a vial: stripes follow the spray split, colors follow each
 * fragrance's accord. Opens the blend in the studio; the menu renames,
 * deletes (with a confirm step), shows the wear history or logs a wear.
 */
export function BlendVial({ stack, onChanged, onOpen, className }: { stack: SavedLayeringStack; onChanged?: () => void; onOpen?: () => void; className?: string }) {
  const router = useRouter();
  const id = useId();
  const [renameOpen, setRenameOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [wears, setWears] = useState<LayeringStackWear[] | null>(null);
  const [name, setName] = useState(stack.name);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const [historyPending, startHistory] = useTransition();
  const members = stackMembers(stack);

  function run(task: () => Promise<unknown>, success: string, after?: () => void) {
    startTransition(async () => {
      try {
        await task();
        setError(null);
        toast.success(success);
        after?.();
        onChanged?.();
        router.refresh();
      } catch {
        setError("That did not save. Try again.");
      }
    });
  }

  function openHistory() {
    setHistoryOpen(true);
    setWears(null);
    startHistory(async () => {
      try {
        setWears(await getLayerStackHistory(stack.id));
      } catch {
        setWears([]);
      }
    });
  }

  return (
    <article className={cn(styles.vial, className)} data-testid="blend-vial">
      <Link href={`/layering?saved=${stack.id}`} className={styles.open} onClick={onOpen}>
        <span className={styles.vialArea}>
          <Vial size="lg" layers={members.map((item) => ({ id: item.fragrance.id, accord: accordFor(item.fragrance), sprays: item.suggested_sprays }))} />
        </span>
        <span className={cn("at-card-title", styles.name)}>{stack.name}</span>
      </Link>
      <span className={cn("at-caption", styles.caption)}>
        {blendCaption(stack)}
        {stack.average_rating !== null ? <> · <span aria-label={`Rated ${stack.average_rating.toFixed(1)} of 5`}>★ {stack.average_rating.toFixed(1)}</span></> : null}
      </span>
      {stack.last_worn_at ? <span className={cn("at-caption", styles.caption)}>Last worn {formatWearDate(stack.last_worn_at)}</span> : null}
      {error ? <p className="at-error" role="alert">{error}</p> : null}
      <DropdownMenu.Root modal={false}>
        <DropdownMenu.Trigger className={styles.more} aria-label={`More actions for ${stack.name}`} disabled={pending}>
          <MoreHorizontal aria-hidden="true" />
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content className={styles.menu} align="end" sideOffset={6} collisionPadding={16}>
            <DropdownMenu.Item className={styles.menuItem} onSelect={() => run(() => logLayerStackWear(stack.id, null, ""), "Blend worn")}>Wear this blend</DropdownMenu.Item>
            <DropdownMenu.Item className={styles.menuItem} onSelect={openHistory}>Wear history</DropdownMenu.Item>
            <DropdownMenu.Item className={styles.menuItem} onSelect={() => { setName(stack.name); setRenameOpen(true); }}>Rename</DropdownMenu.Item>
            <DropdownMenu.Item className={cn(styles.menuItem, styles.danger)} onSelect={() => setDeleteOpen(true)}>Delete</DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>

      <Sheet
        open={renameOpen}
        onOpenChange={setRenameOpen}
        title="Rename blend"
        footer={<div className={styles.actions}><Button type="submit" form={`${id}-rename`} disabled={pending || !name.trim()}>{pending ? "Saving…" : "Save name"}</Button><Button variant="text" onClick={() => setRenameOpen(false)}>Cancel</Button></div>}
      >
        <form id={`${id}-rename`} onSubmit={(event) => { event.preventDefault(); if (name.trim()) run(() => renameLayerStack(stack.id, name.trim()), "Blend renamed", () => setRenameOpen(false)); }}>
          <Field label="Name" htmlFor={`${id}-name`}>
            <TextInput id={`${id}-name`} value={name} maxLength={120} onChange={(event) => setName(event.target.value)} />
          </Field>
        </form>
      </Sheet>

      <Sheet
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title={`Delete ${stack.name}?`}
        description="The blend and its wear history are removed. This cannot be undone."
        footer={<div className={styles.actions}><Button variant="danger" disabled={pending} onClick={() => run(() => deleteLayerStack(stack.id), "Blend deleted", () => setDeleteOpen(false))}>{pending ? "Deleting…" : "Delete blend"}</Button><Button variant="text" onClick={() => setDeleteOpen(false)}>Keep it</Button></div>}
      >
        <p className="at-body">{blendCaption(stack)}</p>
      </Sheet>

      <Sheet open={historyOpen} onOpenChange={setHistoryOpen} title={`${stack.name}: wear history`}>
        {historyPending || wears === null ? (
          <p className="at-body" aria-busy="true">Loading the history…</p>
        ) : wears.length === 0 ? (
          <p className="at-body">Not worn yet. Wear it from the flask or this menu.</p>
        ) : (
          <ol className={styles.history}>
            {wears.map((wear) => (
              <li key={wear.id}>
                <span>{formatWearDate(wear.worn_at)}</span>
                {wear.rating !== null ? <span aria-label={`Rated ${wear.rating} of 5`}>★ {wear.rating}</span> : null}
                {wear.notes ? <span className="at-caption">{wear.notes}</span> : null}
              </li>
            ))}
          </ol>
        )}
      </Sheet>
    </article>
  );
}
