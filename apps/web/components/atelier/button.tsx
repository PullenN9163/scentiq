import { Slot } from "@radix-ui/react-slot";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

import styles from "./button.module.css";

export type ButtonVariant = "primary" | "soft" | "outline" | "text" | "danger";
export type ButtonSize = "default" | "sm";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  asChild?: boolean;
};

/**
 * Atelier pill button. One primary per view; labels in sentence case.
 * `asChild` renders the styles onto a child such as a link.
 */
export function Button({ asChild, className, variant = "primary", size = "default", type, ...props }: ButtonProps) {
  const Component = asChild ? Slot : "button";
  return (
    <Component
      className={cn(styles.button, styles[variant], size === "sm" && styles.sm, className)}
      data-variant={variant}
      data-size={size}
      {...(asChild ? {} : { type: type ?? "button" })}
      {...props}
    />
  );
}
