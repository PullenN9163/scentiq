import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import styles from "./states.module.css";

/** A serif line, one sentence and one action, directly on the ground. */
export function AtelierEmpty({
  title,
  children,
  action,
  headingLevel = 2,
  className,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  headingLevel?: 1 | 2 | 3;
  className?: string;
}) {
  const Heading = `h${headingLevel}` as "h1" | "h2" | "h3";
  return (
    <section className={cn(styles.empty, className)}>
      <Heading className="at-title">{title}</Heading>
      {children ? <p className={styles.body}>{children}</p> : null}
      {action}
    </section>
  );
}

/** What happened and what to do, in danger with a word, inline where it occurred. */
export function AtelierError({
  title = "Something went wrong",
  message,
  retry,
  className,
}: {
  title?: string;
  message: string;
  retry?: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn(styles.error, className)} role="alert">
      <h2 className="at-title">{title}</h2>
      <p className={styles.danger}>{message}</p>
      {retry}
    </section>
  );
}

/** Route-level error for pages when the service is unreachable. */
export function AtelierUnavailable({ retry }: { retry?: ReactNode }) {
  return (
    <div className="at-page">
      <AtelierError title="ScentIQ is unavailable" message="ScentIQ could not reach the service. Your data is unchanged; try again in a moment." retry={retry} />
    </div>
  );
}
