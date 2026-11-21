import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

import styles from "./chip.module.css";

type ReadOnlyChipProps = HTMLAttributes<HTMLSpanElement> & {
  variant?: "context" | "note";
  children: ReactNode;
};

type ChoiceChipProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> & {
  variant: "choice";
  pressed: boolean;
  children: ReactNode;
};

/**
 * Short facts and choices. Context and note chips are read-only text; choice
 * chips are toggle buttons that expose `aria-pressed`.
 */
export function Chip(props: ReadOnlyChipProps | ChoiceChipProps) {
  if (props.variant === "choice") {
    const { pressed, className, children, type, variant, ...rest } = props;
    return (
      <button
        type={type ?? "button"}
        aria-pressed={pressed}
        data-variant={variant}
        className={cn(styles.chip, styles.choice, pressed && styles.pressed, className)}
        {...rest}
      >
        {children}
      </button>
    );
  }
  const { variant = "context", className, children, ...rest } = props;
  return (
    <span data-variant={variant} className={cn(styles.chip, styles[variant], className)} {...rest}>
      {children}
    </span>
  );
}
