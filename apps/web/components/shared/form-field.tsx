"use client";

import type { ReactNode } from "react";

import type { ActionState } from "@/lib/action-state";

/**
 * A labelled field that renders its own error and keeps the submitted value.
 *
 * `defaultValue` is read from the action result first, so a failed submit
 * re-renders with what the user typed rather than clearing the form.
 */
export function Field({
  name,
  label,
  state,
  fallbackValue = "",
  children,
  hint,
}: {
  name: string;
  label: string;
  state: ActionState;
  fallbackValue?: string;
  hint?: string;
  children: (props: {
    id: string;
    name: string;
    defaultValue: string;
    "aria-invalid": boolean | undefined;
    "aria-describedby": string | undefined;
  }) => ReactNode;
}) {
  const error = state.fieldErrors?.[name];
  const id = `field-${name}`;
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  const describedBy = [error ? errorId : null, hint ? hintId : null].filter(Boolean).join(" ");

  return (
    <div className="field">
      <label className="label" htmlFor={id}>
        {label}
      </label>
      {children({
        id,
        name,
        defaultValue: state.values?.[name] ?? fallbackValue,
        "aria-invalid": error ? true : undefined,
        "aria-describedby": describedBy || undefined,
      })}
      {hint ? (
        <span className="field-hint" id={hintId}>
          {hint}
        </span>
      ) : null}
      {error ? (
        <span className="field-error" id={errorId} role="alert">
          {error}
        </span>
      ) : null}
    </div>
  );
}

/** The action's overall outcome, announced to assistive technology. */
export function FormMessage({ state }: { state: ActionState }) {
  if (state.status === "idle" || !state.message) {
    return null;
  }
  return (
    <p
      className={`form-message form-message--${state.status === "success" ? "success" : "error"}`}
      role={state.status === "error" ? "alert" : "status"}
    >
      {state.message}
    </p>
  );
}
