"use client";

import { useActionState, useState } from "react";

import { Field, FormMessage } from "@/components/shared/form-field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { idleState } from "@/lib/action-state";
import { deleteAccount } from "@/lib/server/actions";

/**
 * Account deletion, behind an explicit typed confirmation.
 *
 * The action marks the account pending, deletes the sign-in identity, and rolls
 * the pending mark back if that fails — so a failure leaves the account usable
 * rather than stranded.
 */
export function DeleteAccountPanel() {
  const [confirming, setConfirming] = useState(false);
  const [state, action, pending] = useActionState(deleteAccount, idleState);

  if (state.status === "success") {
    return (
      <p className="success-note" role="status">
        {state.message} You will be signed out shortly.
      </p>
    );
  }

  if (!confirming) {
    return (
      <Button variant="danger" type="button" onClick={() => setConfirming(true)}>
        Delete my account
      </Button>
    );
  }

  return (
    <form className="stack" action={action} noValidate>
      <FormMessage state={state} />
      <p className="muted">
        This permanently removes your collection, wear history, preferences and custom fragrances.
        It cannot be undone.
      </p>
      <Field
        name="confirmation"
        label="Type “delete” to confirm"
        state={state}
        hint="This is the last step before your data is removed."
      >
        {(props) => <Input type="text" autoComplete="off" {...props} />}
      </Field>
      <div className="cluster">
        <Button variant="danger" type="submit" disabled={pending}>
          {pending ? "Deleting…" : "Permanently delete"}
        </Button>
        <Button type="button" variant="ghost" onClick={() => setConfirming(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
