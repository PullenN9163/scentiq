"use client";

import { Compass } from "lucide-react";

import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function DiscoverError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <section className="page">
      <PageHeader
        eyebrow="Beyond the shelf"
        title="Discover"
        description="Source-backed recommendations scored against your owned collection."
      />
      <Card>
        <CardContent className="empty-panel">
          <Compass />
          <h2>Recommendations are taking a moment</h2>
          <p>Your collection is safe. Try loading its recommendations again.</p>
          <Button type="button" onClick={reset}>Try again</Button>
        </CardContent>
      </Card>
    </section>
  );
}
