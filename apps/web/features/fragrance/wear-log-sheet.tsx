"use client";

import { useRouter } from "next/navigation";
import { useActionState, useId } from "react";
import { toast } from "sonner";

import { Button } from "@/components/atelier/button";
import { Field, Select, TextArea, TextInput } from "@/components/atelier/field";
import { Sheet } from "@/components/atelier/sheet";
import { idleState, type ActionState } from "@/lib/action-state";
import { logWear } from "@/lib/server/actions";

import styles from "./fragrance.module.css";

const OCCASIONS = [["work", "Work"], ["casual", "Casual"], ["date", "Date"], ["dinner", "Dinner"], ["party", "Party"], ["formal", "Formal"], ["gym", "Gym"], ["travel", "Travel"], ["other", "Other"]] as const;

/** A datetime-local value for "now", which the input requires unzoned. */
function nowForInput(): string {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
}

function valueOf(state: ActionState, name: string, fallback: string): string {
  return state.values?.[name] ?? fallback;
}

/**
 * Log a wear of an owned item with the existing logWear action and its
 * fields (when, sprays, occasion, setting, notes).
 */
export function WearLogSheet({
  itemId,
  fragranceName,
  open,
  onOpenChange,
  onLogged,
}: {
  itemId: string;
  fragranceName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onLogged?: () => void;
}) {
  const router = useRouter();
  const id = useId();
  const [state, action, pending] = useActionState(async (previous: ActionState, form: FormData) => {
    const localTime = String(form.get("worn_at") ?? "");
    const instant = new Date(localTime);
    // Resolve datetime-local in the member's browser, as the existing view does.
    form.set("worn_at", Number.isNaN(instant.getTime()) ? "" : instant.toISOString());
    const result = await logWear(previous, form);
    if (result.status === "success") {
      onOpenChange(false);
      toast.success(result.message ?? "Wear logged.");
      router.refresh();
      onLogged?.();
    }
    return result.values ? { ...result, values: { ...result.values, worn_at: localTime } } : result;
  }, idleState);

  return (
    <Sheet
      open={open}
      onOpenChange={onOpenChange}
      title={`Wear ${fragranceName}`}
      footer={<div className={styles.sheetActions}><Button type="submit" form={`${id}-wear`} disabled={pending}>{pending ? "Saving…" : "Log wear"}</Button><Button variant="text" onClick={() => onOpenChange(false)}>Cancel</Button></div>}
    >
      <form id={`${id}-wear`} action={action} className={styles.form} noValidate>
        {state.status === "error" && state.message ? <p className={styles.error} role="alert">{state.message}</p> : null}
        <input type="hidden" name="collection_item_id" value={itemId} />
        <Field label="When" htmlFor={`${id}-worn`} error={state.fieldErrors?.worn_at}>
          <TextInput id={`${id}-worn`} name="worn_at" type="datetime-local" defaultValue={valueOf(state, "worn_at", nowForInput())} />
        </Field>
        <Field label="Sprays" htmlFor={`${id}-sprays`} error={state.fieldErrors?.sprays}>
          <TextInput id={`${id}-sprays`} name="sprays" type="number" inputMode="numeric" min={1} max={30} defaultValue={valueOf(state, "sprays", "")} />
        </Field>
        <Field label="Occasion" htmlFor={`${id}-occasion`} error={state.fieldErrors?.occasion}>
          <Select id={`${id}-occasion`} name="occasion" defaultValue={valueOf(state, "occasion", "")}>
            <option value="">No occasion</option>
            {OCCASIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </Select>
        </Field>
        <Field label="Setting" htmlFor={`${id}-setting`} error={state.fieldErrors?.setting}>
          <TextInput id={`${id}-setting`} name="setting" maxLength={40} defaultValue={valueOf(state, "setting", "")} />
        </Field>
        <Field label="Notes" htmlFor={`${id}-notes`} error={state.fieldErrors?.notes}>
          <TextArea id={`${id}-notes`} name="notes" rows={3} defaultValue={valueOf(state, "notes", "")} />
        </Field>
      </form>
    </Sheet>
  );
}
