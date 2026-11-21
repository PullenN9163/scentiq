"use client";

import { Minus, Plus } from "lucide-react";
import { useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

import styles from "./field.module.css";

/** Label above, control, then an optional hint or error below. */
export function Field({
  label,
  htmlFor,
  hint,
  error,
  children,
  className,
}: {
  label: ReactNode;
  htmlFor?: string;
  hint?: ReactNode;
  error?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn(styles.field, className)}>
      <label className={styles.label} htmlFor={htmlFor}>{label}</label>
      {children}
      {error ? <p className={styles.error} role="alert">{error}</p> : hint ? <p className={cn("at-caption", styles.hint)}>{hint}</p> : null}
    </div>
  );
}

export function TextInput({ className, invalid, ...props }: InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) {
  return <input className={cn(styles.input, invalid && styles.invalid, className)} aria-invalid={invalid || undefined} {...props} />;
}

export function TextArea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(styles.input, styles.textarea, className)} {...props} />;
}

export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cn(styles.input, styles.select, className)} {...props}>{children}</select>;
}

/** A − / + stepper for small whole numbers such as sprays. */
export function Stepper({
  value,
  onChange,
  min,
  max,
  label,
  name,
  id,
}: {
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  label: string;
  name?: string;
  id?: string;
}) {
  const fallbackId = useId();
  const inputId = id ?? fallbackId;
  const clamp = (next: number) => Math.min(max, Math.max(min, next));
  return (
    <div className={styles.stepper}>
      <button type="button" className={styles.stepButton} aria-label={`Fewer ${label.toLowerCase()}`} disabled={value <= min} onClick={() => onChange(clamp(value - 1))}>
        <Minus aria-hidden="true" />
      </button>
      <input
        id={inputId}
        name={name}
        className={styles.stepValue}
        type="number"
        inputMode="numeric"
        min={min}
        max={max}
        step={1}
        value={Number.isFinite(value) ? value : ""}
        aria-label={label}
        onChange={(event) => onChange(event.target.value === "" ? Number.NaN : Number(event.target.value))}
        onBlur={() => { if (Number.isFinite(value)) onChange(clamp(Math.round(value))); }}
      />
      <button type="button" className={styles.stepButton} aria-label={`More ${label.toLowerCase()}`} disabled={value >= max} onClick={() => onChange(clamp((Number.isFinite(value) ? value : min - 1) + 1))}>
        <Plus aria-hidden="true" />
      </button>
    </div>
  );
}

/** A switch for settings that apply immediately. */
export function Switch({
  checked,
  onCheckedChange,
  label,
  name,
  disabled,
}: {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label: string;
  name?: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      className={styles.switch}
      data-checked={checked ? "true" : "false"}
      onClick={() => onCheckedChange(!checked)}
    >
      {name ? <input type="hidden" name={name} value={checked ? "on" : ""} /> : null}
      <span className={styles.switchThumb} aria-hidden="true" />
    </button>
  );
}
