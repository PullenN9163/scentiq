"use client";

import { CloudSun, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { type CalendarResult, formatEventTime, occasionLabel } from "@/lib/calendar";
import { rankFragrances } from "@/lib/catalog-ranking";
import { toneFor } from "@/lib/tone";
import { conditionLabel, formatTemperature, type WeatherResult } from "@/lib/weather";
import { contextFor, type PlanDay } from "@/lib/week";
import type { FragranceDetail, TemperatureUnit } from "@/types/api";

function dayLabel(date: string, options: Intl.DateTimeFormatOptions): string {
  return new Date(`${date}T12:00:00Z`).toLocaleDateString("en-US", { ...options, timeZone: "UTC" });
}

/**
 * The next seven days, each matched to a fragrance from the owned collection
 * using that day's forecast and calendar. Every input is optional: a day
 * without a forecast or events is still planned, from the season alone.
 */
export function WeekPlanner({
  owned,
  days,
  timeZone,
  temperatureUnit,
  weatherStatus,
  calendarStatus,
  needsReconnect = false,
}: {
  owned: FragranceDetail[];
  days: PlanDay[];
  timeZone: string;
  temperatureUnit: TemperatureUnit;
  weatherStatus: WeatherResult["status"];
  calendarStatus: CalendarResult["status"];
  needsReconnect?: boolean;
}) {
  const [offsets, setOffsets] = useState<Record<string, number>>({});
  const range =
    days.length > 0
      ? `${dayLabel(days[0].date, { month: "short", day: "numeric" })} – ${dayLabel(days[days.length - 1].date, { month: "short", day: "numeric" })}`
      : "This week";

  return (
    <section className="page">
      <PageHeader
        eyebrow={range}
        title="My Week"
        description="Your owned fragrances matched to each day's forecast and plans."
      />
      <PlanningNotes
        weatherStatus={weatherStatus}
        calendarStatus={calendarStatus}
        needsReconnect={needsReconnect}
      />
      {owned.length === 0 ? (
        <Card className="empty-panel">
          <h2>Your collection is empty</h2>
          <p>Add an owned fragrance before planning a week.</p>
          <Button asChild>
            <Link href="/collection">Open collection</Link>
          </Button>
        </Card>
      ) : (
        <div className="week-list">
          {days.map((day) => {
            const ranked = rankFragrances(owned, contextFor(day, timeZone));
            const index = (offsets[day.date] ?? 0) % ranked.length;
            const fragrance = ranked[index];
            return (
              <Card key={day.date} className="day-card" data-testid="week-day">
                <div className="day-card__date">
                  <strong>{dayLabel(day.date, { weekday: "long" })}</strong>
                  {day.weather ? (
                    <span>
                      <CloudSun size={16} />
                      {formatTemperature(day.weather.high_celsius, temperatureUnit)} ·{" "}
                      {conditionLabel(day.weather.condition)}
                    </span>
                  ) : null}
                </div>
                <div className="day-card__events">
                  {day.events.length ? (
                    day.events.map((event) => (
                      <span key={event.id}>
                        <strong>{formatEventTime(event, timeZone)}</strong>
                        {event.title}
                        {event.occasion === "other" ? null : (
                          <Badge>{occasionLabel(event.occasion)}</Badge>
                        )}
                      </span>
                    ))
                  ) : (
                    <span className="muted">Open day</span>
                  )}
                </div>
                <div
                  className="day-card__scent"
                  style={{ "--scent-tone": toneFor(fragrance.id) } as React.CSSProperties}
                >
                  <span className="scent-swatch" />
                  <div>
                    <Badge>Collection match</Badge>
                    <h2 className="serif">{fragrance.name}</h2>
                    <p>
                      {fragrance.brand.name} · {fragrance.projection_level ?? "projection unknown"}
                    </p>
                  </div>
                </div>
                <div className="day-card__actions">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() =>
                      setOffsets((current) => ({ ...current, [day.date]: index + 1 }))
                    }
                  >
                    <RefreshCw size={15} />
                    Alternative
                  </Button>
                  <Button asChild size="sm" variant="ghost">
                    <Link href={`/collection/${fragrance.id}`}>Details</Link>
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </section>
  );
}

/** Says which inputs are missing, and where to fix that. */
function PlanningNotes({
  weatherStatus,
  calendarStatus,
  needsReconnect,
}: {
  weatherStatus: WeatherResult["status"];
  calendarStatus: CalendarResult["status"];
  needsReconnect: boolean;
}) {
  const notes: React.ReactNode[] = [];
  if (weatherStatus === "location_required" || weatherStatus === "location_unresolved") {
    notes.push(
      <span key="weather">
        <Link href="/settings">Add your location</Link> to plan around the forecast.
      </span>,
    );
  } else if (weatherStatus === "unavailable") {
    notes.push(<span key="weather">The forecast is unavailable right now.</span>);
  }
  if (calendarStatus === "not_connected") {
    notes.push(
      <span key="calendar">
        <Link href="/settings#calendar">Connect a calendar</Link> to plan around your events.
      </span>,
    );
  } else if (calendarStatus === "unavailable") {
    notes.push(<span key="calendar">Your calendar can&apos;t be loaded right now.</span>);
  } else if (needsReconnect) {
    notes.push(
      <span key="calendar">
        A calendar needs <Link href="/settings#calendar">reconnecting</Link>.
      </span>,
    );
  }
  if (notes.length === 0) return null;
  return (
    <p className="muted planning-notes" role="status">
      {notes.map((note, index) => (
        <span key={index}>
          {index > 0 ? " " : null}
          {note}
        </span>
      ))}
    </p>
  );
}
