import type { ReactNode } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * The shared empty / loading / error / preview states.
 *
 * These reuse the existing card and skeleton primitives so connecting real data
 * does not introduce a second visual language.
 */

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <Card>
      <CardContent className="state-block">
        <p className="state-block__title">{title}</p>
        <p className="state-block__body">{description}</p>
        {action}
      </CardContent>
    </Card>
  );
}

export function LoadingState({ rows = 3, label }: { rows?: number; label: string }) {
  return (
    <div className="state-block" aria-busy="true" aria-live="polite">
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} className="state-block__skeleton" />
      ))}
    </div>
  );
}

/** Shown when the service could not be reached; `retry` re-runs the segment. */
export function UnavailableState({
  message = "ScentIQ could not reach the service.",
  retry,
}: {
  message?: string;
  retry?: ReactNode;
}) {
  return (
    <Card>
      <CardContent className="state-block" role="alert">
        <p className="state-block__title">Service unavailable</p>
        <p className="state-block__body">{message}</p>
        {retry}
      </CardContent>
    </Card>
  );
}

export function ErrorState({ message, retry }: { message: string; retry?: ReactNode }) {
  return (
    <Card>
      <CardContent className="state-block" role="alert">
        <p className="state-block__title">Something went wrong</p>
        <p className="state-block__body">{message}</p>
        {retry}
      </CardContent>
    </Card>
  );
}

/**
 * Marks a surface that is not backed by persisted data.
 *
 * Preview areas must say so plainly, so nothing here implies that an action was
 * durably saved.
 */
export function PreviewNotice({ children }: { children: ReactNode }) {
  return (
    <p className="preview-notice" role="note">
      <span className="preview-notice__tag">Preview</span>
      <span>{children}</span>
    </p>
  );
}
