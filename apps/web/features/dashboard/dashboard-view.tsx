"use client";

import Link from "next/link";

import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/states";
import { RecommendationCard } from "@/features/recommendations/recommendation-card";
import type { WearPlan } from "@/types/wear-intelligence";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EventsCard } from "@/features/dashboard/events-card";
import { WeatherCard } from "@/features/dashboard/weather-card";
import type { CalendarResult } from "@/lib/calendar";
import type { WeatherResult } from "@/lib/weather";
import type { CollectionInsights, Me, WearLogEntry } from "@/types/api";

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
  weather,
  calendar,
  timeZone,
  plan,
}: {
  plan?: WearPlan;
  me: Me;
  insights: CollectionInsights;
  recentWears: WearLogEntry[];
  weather: WeatherResult;
  /** Already narrowed to today in `timeZone`. */
  calendar: CalendarResult;
  timeZone: string;
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

      {plan?.recommendations.map(recommendation => <RecommendationCard key={recommendation.context_key} recommendation={recommendation}/>)}
      {plan && plan.recommendations.length === 0 && <p>Add an owned fragrance to receive recommendations.</p>}
      {plan?.gaps.map(gap => <p className="muted" key={gap}>{gap}</p>)}
      <div className="grid grid-2 detail-sections"><WeatherCard weather={weather}/><EventsCard calendar={calendar} timeZone={timeZone}/></div>

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


    </section>
  );
}
