"use client";

import { useEffect } from "react";

import { AtelierError } from "@/components/atelier/states";
import { ErrorState } from "@/components/shared/states";
import { Button as AtelierButton } from "@/components/atelier/button";
import { Button } from "@/components/ui/button";

/** A failed page offers a retry in place instead of a blank crash and a manual refresh. */
export default function AppError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  const atelier = typeof document !== "undefined" && document.documentElement.dataset.atelier === "true";
  const message = "This page could not load. Your data is safe; try again in a moment.";
  if (atelier) {
    return (
      <div className="at-page">
        <AtelierError message={message} retry={<AtelierButton variant="outline" onClick={reset}>Try again</AtelierButton>} />
      </div>
    );
  }
  return (
    <section className="page">
      <ErrorState message={message} retry={<Button variant="secondary" onClick={reset}>Try again</Button>} />
    </section>
  );
}
