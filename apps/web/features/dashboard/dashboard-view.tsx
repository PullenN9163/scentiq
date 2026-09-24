"use client";

import { CalendarDays, CloudSun, Sparkles } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/shared/page-header";
import { EmptyState, PreviewNotice } from "@/components/shared/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { CollectionInsights, Me, WearLogEntry } from "@/types/api";

/**
 * The Today screen.
 *
 * Collection totals and recent wears are real. Weather, events and the
 * recommendation remain previews and are labelled as such, because no provider
 * or engine is connected yet.
 */

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
}

export function DashboardView({
  me,
  insights,
  recentWears,
}: {
  me: Me;
  insights: CollectionInsights;
  recentWears: WearLogEntry[];
}) {
  const location = me.preferences.location;

  if (insights.total_items === 0) {
    return (
      <section className="page">
        <PageHeader
          eyebrow="Welcome"
          title={`Hello, ${me.display_name}`}
          description="Your collection is empty, so there is nothing to plan around yet."
        />
        <EmptyState
          title="Add your first fragrance"
          description="Once you have a bottle, decant or sample saved, ScentIQ can start tracking wears and building your collection picture."
          action={
            <Button asChild>
              <Link href="/collection">Go to collection</Link>
            </Button>
          }
        />
      </section>
    );
  }

  return (
    <section className="page">
      <PageHeader
        eyebrow="Today"
        title={`Hello, ${me.display_name}`}
        description={
          location
            ? `${location} · ${insights.owned_items} owned · ${insights.total_wears} wears logged`
            : `${insights.owned_items} owned · ${insights.total_wears} wears logged`
        }
      />

      <div className="metric-grid">
        <Card>
          <CardContent>
            <span>In collection</span>
            <strong className="metric-number">{insights.total_items}</strong>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <span>Owned</span>
            <strong className="metric-number">{insights.owned_items}</strong>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <span>Wears (30 days)</span>
            <strong className="metric-number">{insights.wears_last_30_days}</strong>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <span>Worn at least once</span>
            <strong className="metric-number">{insights.distinct_fragrances_worn}</strong>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-2 detail-sections">
        <Card>
          <CardContent>
            <p className="eyebrow">Rotation context</p>
            <h2 className="serif">Recently worn</h2>
            {recentWears.length === 0 ? (
              <p className="muted">
                No wears logged yet. Open a fragrance in your collection to log one.
              </p>
            ) : (
              recentWears.slice(0, 6).map((wear) => (
                <p key={wear.id}>
                  <strong>{wear.fragrance_name}</strong> · {formatDate(wear.worn_at)}
                  {wear.sprays === null ? "" : ` · ${wear.sprays} sprays`}
                </p>
              ))
            )}
            <Button asChild variant="ghost">
              <Link href="/collection">Open collection</Link>
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <p className="eyebrow">Most worn</p>
            <h2 className="serif">What you reach for</h2>
            {insights.most_worn.length === 0 ? (
              <p className="muted">Log a few wears and your rotation will show up here.</p>
            ) : (
              insights.most_worn.slice(0, 5).map((entry) => (
                <p key={entry.collection_item_id}>
                  <strong>{entry.fragrance_name}</strong> · {entry.brand_name} ·{" "}
                  {entry.wear_count} {entry.wear_count === 1 ? "wear" : "wears"}
                </p>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-3 detail-sections">
        <Card>
          <CardContent>
            <div className="section-title">
              <Sparkles size={19} />
              <h3>Recommendation</h3>
            </div>
            <PreviewNotice>Not connected yet — nothing here is personalised or saved.</PreviewNotice>
            <p className="muted">
              Daily recommendations arrive once the scoring engine is connected. Your collection and
              wear history are already being recorded, which is what it will use.
            </p>
            <Badge>Preview</Badge>
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <div className="section-title">
              <CloudSun size={19} />
              <h3>Weather</h3>
            </div>
            <PreviewNotice>No weather provider is connected.</PreviewNotice>
            <p className="muted">
              {location
                ? `Your saved location is ${location}. Forecasts will use it once a provider is connected.`
                : "Add a location in Settings and forecasts will use it once a provider is connected."}
            </p>
            <Button asChild variant="ghost">
              <Link href="/settings">Open settings</Link>
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <div className="section-title">
              <CalendarDays size={19} />
              <h3>Events</h3>
            </div>
            <PreviewNotice>No calendar is connected.</PreviewNotice>
            <p className="muted">
              Calendar-aware planning is not available yet, so no events are shown.
            </p>
            <Badge>Preview</Badge>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
