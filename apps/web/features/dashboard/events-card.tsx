import { CalendarDays } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { type CalendarResult, formatEventTime, occasionLabel } from "@/lib/calendar";

/** Today's events from the member's connected calendars. */
export function EventsCard({
  calendar,
  timeZone,
}: {
  calendar: CalendarResult;
  timeZone: string;
}) {
  return (
    <Card>
      <CardContent>
        <div className="section-title">
          <CalendarDays size={19} />
          <h3>Today&apos;s events</h3>
        </div>
        <EventsBody calendar={calendar} timeZone={timeZone} />
      </CardContent>
    </Card>
  );
}

function EventsBody({ calendar, timeZone }: { calendar: CalendarResult; timeZone: string }) {
  if (calendar.status === "not_connected") {
    return (
      <>
        <p className="muted">Connect Google or Outlook to plan fragrances around your day.</p>
        <Button asChild variant="ghost">
          <Link href="/settings#calendar">Connect a calendar</Link>
        </Button>
      </>
    );
  }

  if (calendar.status === "unavailable") {
    return (
      <p className="muted" role="status">
        Your calendar can&apos;t be loaded right now. Try again shortly.
      </p>
    );
  }

  return (
    <>
      {calendar.events.length === 0 ? (
        <p className="muted">Nothing scheduled today — an open day.</p>
      ) : (
        <ul className="event-list">
          {calendar.events.map((event) => (
            <li key={event.id}>
              <span className="event-list__time">{formatEventTime(event, timeZone)}</span>
              <span>
                <strong>{event.title}</strong> <Badge>{occasionLabel(event.occasion)}</Badge>
              </span>
            </li>
          ))}
        </ul>
      )}
      {calendar.needsReconnect ? (
        <p className="muted" role="status">
          A calendar needs reconnecting.{" "}
          <Link href="/settings#calendar">Open settings</Link>
        </p>
      ) : null}
    </>
  );
}
