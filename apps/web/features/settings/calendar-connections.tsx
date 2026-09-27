"use client";

import { CalendarDays, RefreshCw } from "lucide-react";
import { useActionState, useRef, useState } from "react";

import { FormMessage } from "@/components/shared/form-field";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { idleState } from "@/lib/action-state";
import { CALENDAR_NOTICES, PROVIDER_LABELS } from "@/lib/calendar";
import {
  disconnectCalendar,
  setCalendarSelected,
  syncCalendarConnection,
} from "@/lib/server/actions";
import type {
  CalendarConnection,
  CalendarProviderStatus,
  CalendarSource,
} from "@/types/api";

/**
 * Connected Google and Outlook calendars.
 *
 * Connecting is a full-page navigation to a route handler, never a prefetched
 * link, because it starts an OAuth redirect. Only the calendars ticked here
 * feed Today and planning.
 */
export function CalendarConnectionsCard({
  providers,
  connections,
  notice,
}: {
  providers: CalendarProviderStatus[] | null;
  connections: CalendarConnection[] | null;
  notice: string | null;
}) {
  const noticeContent = notice ? CALENDAR_NOTICES[notice] : undefined;

  return (
    <Card id="calendar">
      <CardContent>
        <div className="settings-title">
          <CalendarDays size={19} />
          <h2>Calendar connections</h2>
        </div>
        {noticeContent ? (
          <p
            className={`form-message form-message--${noticeContent.tone}`}
            role={noticeContent.tone === "error" ? "alert" : "status"}
          >
            {noticeContent.message}
          </p>
        ) : null}

        {providers === null || connections === null ? (
          <p className="muted" role="status">
            Calendar connections can&apos;t be loaded right now. Try again shortly.
          </p>
        ) : (
          <>
            <p className="muted">
              ScentIQ reads event titles and times only, to plan around your day. It never
              stores descriptions, attendees or meeting links.
            </p>
            {connections.map((connection) => (
              <ConnectionPanel key={connection.id} connection={connection} />
            ))}
            {providers.map((status) =>
              status.available ? (
                <a
                  key={status.provider}
                  className="connection-row"
                  href={`/integrations/calendar/${status.provider}/start`}
                >
                  <span>
                    {connections.some((c) => c.provider === status.provider)
                      ? `Connect another ${PROVIDER_LABELS[status.provider]} account`
                      : `Connect ${PROVIDER_LABELS[status.provider]}`}
                  </span>
                  <Badge>Connect</Badge>
                </a>
              ) : (
                <button key={status.provider} className="connection-row" disabled type="button">
                  <span>{PROVIDER_LABELS[status.provider]}</span>
                  <Badge>Unavailable</Badge>
                </button>
              ),
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function formatSynced(value: string | null): string {
  if (!value) return "Not synced yet";
  return `Synced ${new Date(value).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  })}`;
}

function ConnectionPanel({ connection }: { connection: CalendarConnection }) {
  const [syncState, syncAction, syncing] = useActionState(syncCalendarConnection, idleState);
  const [disconnectState, disconnectAction, disconnecting] = useActionState(
    disconnectCalendar,
    idleState,
  );
  const [confirming, setConfirming] = useState(false);
  const needsReconnect = connection.status === "reauth_required";

  return (
    <section className="calendar-connection" aria-label={connection.account_email}>
      <div className="calendar-connection__header">
        <span>
          <strong>{PROVIDER_LABELS[connection.provider]}</strong>
          <small>{connection.account_email}</small>
        </span>
        <Badge>{needsReconnect ? "Reconnect needed" : "Connected"}</Badge>
      </div>
      <p className="field-hint">
        {formatSynced(connection.last_synced_at)}
        {!needsReconnect && connection.last_error_code
          ? " · the last sync failed, so saved events are shown"
          : ""}
      </p>
      {needsReconnect ? (
        <p className="muted">
          ScentIQ lost access to this calendar. Reconnect to keep your events up to date.
        </p>
      ) : null}

      <FormMessage state={syncState} />
      <FormMessage state={disconnectState} />

      {connection.sources.length > 0 ? (
        <fieldset className="calendar-connection__sources">
          <legend className="label">Calendars to include</legend>
          {connection.sources.map((source) => (
            <SourceToggle key={source.id} connectionId={connection.id} source={source} />
          ))}
        </fieldset>
      ) : null}

      <div className="cluster">
        {needsReconnect ? (
          <Button asChild size="sm">
            <a href={`/integrations/calendar/${connection.provider}/start`}>Reconnect</a>
          </Button>
        ) : (
          <form action={syncAction}>
            <input type="hidden" name="connection_id" value={connection.id} />
            <Button size="sm" variant="secondary" type="submit" disabled={syncing}>
              <RefreshCw size={15} />
              {syncing ? "Syncing…" : "Sync now"}
            </Button>
          </form>
        )}
        {confirming ? (
          <form action={disconnectAction} className="cluster">
            <input type="hidden" name="connection_id" value={connection.id} />
            <Button size="sm" variant="danger" type="submit" disabled={disconnecting}>
              {disconnecting ? "Disconnecting…" : "Confirm disconnect"}
            </Button>
            <Button size="sm" variant="ghost" type="button" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
          </form>
        ) : (
          <Button size="sm" variant="ghost" type="button" onClick={() => setConfirming(true)}>
            Disconnect
          </Button>
        )}
      </div>
    </section>
  );
}

function SourceToggle({ connectionId, source }: { connectionId: string; source: CalendarSource }) {
  const [state, action, pending] = useActionState(setCalendarSelected, idleState);
  const form = useRef<HTMLFormElement>(null);
  // Shows the requested value while saving; the refreshed props settle it, and
  // a failed save falls back to the stored value.
  const checked = pending ? !source.is_selected : source.is_selected;

  return (
    <form ref={form} action={action} className="toggle-row">
      <input type="hidden" name="connection_id" value={connectionId} />
      <input type="hidden" name="source_id" value={source.id} />
      <input type="hidden" name="is_selected" value={String(!source.is_selected)} />
      <span>
        <strong>{source.name}</strong>
        <small>
          {source.is_primary ? "Main calendar" : "Shared or secondary"}
          {state.status === "error" ? ` · ${state.message}` : ""}
        </small>
      </span>
      <input
        type="checkbox"
        aria-label={`Include ${source.name}`}
        checked={checked}
        disabled={pending}
        onChange={() => form.current?.requestSubmit()}
      />
    </form>
  );
}
