"use client";

import { CalendarDays } from "lucide-react";
import Link from "next/link";
import { useActionState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { type CalendarResult, formatEventTime, occasionLabel } from "@/lib/calendar";
import { idleState } from "@/lib/action-state";
import { updateCalendarEvent } from "@/lib/server/actions";
import type { CalendarEvent } from "@/types/api";

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
              <div>
                <strong>{event.title}</strong> <Badge>{occasionLabel(event.occasion)}</Badge>
                {event.classification_source === "ai" ? <span className="muted"> · AI interpreted</span> : null}
                <EventDetails event={event} />
              </div>
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

function EventDetails({ event }: { event: CalendarEvent }) {
  const [state, action, pending] = useActionState(updateCalendarEvent, idleState);
  return (
    <details>
      <summary>Correct event details</summary>
      <form action={action} className="form-grid">
        <input type="hidden" name="event_id" value={event.id} />
        <label htmlFor={`occasion-${event.id}`}>Occasion</label>
        <select id={`occasion-${event.id}`} name="occasion" defaultValue={event.occasion}>
          <option value="work">Work / office</option>
          <option value="casual">Casual outing</option>
          <option value="formal">Formal event</option>
          <option value="date">Date night</option>
          <option value="party">Party / celebration</option>
          <option value="gym">Gym / exercise</option>
          <option value="travel">Travel / transit</option>
          <option value="dinner">Dinner / restaurant</option>
          <option value="other">Other occasion</option>
        </select>
        <label htmlFor={`formality-${event.id}`}>Formality</label>
        <select id={`formality-${event.id}`} name="formality" defaultValue={event.formality ?? ""}>
          <option value="">Unspecified</option>
          <option value="casual">Casual</option>
          <option value="smart">Smart</option>
          <option value="formal">Formal</option>
        </select>
        <label htmlFor={`setting-${event.id}`}>Setting</label>
        <select id={`setting-${event.id}`} name="setting" defaultValue={event.setting ?? ""}>
          <option value="">Unspecified</option>
          <option value="indoor">Indoors</option>
          <option value="outdoor">Outdoors</option>
          <option value="mixed">Indoors and outdoors</option>
        </select>
        <Button type="submit" disabled={pending} variant="ghost">
          {pending ? "Saving…" : "Save event details"}
        </Button>
        {event.classification_corrected ? <p className="muted">Your event details are saved through calendar sync.</p> : null}
        {state.message ? <p role={state.status === "error" ? "alert" : "status"}>{state.message}</p> : null}
      </form>
    </details>
  );
}
