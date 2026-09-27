import { Suspense } from "react";

import { ErrorState, LoadingState, UnavailableState } from "@/components/shared/states";
import { SettingsView } from "@/features/settings/settings-view";
import { ApiError } from "@/lib/server/api-client";
import { getCalendarConnections, getCalendarProviders, getMe } from "@/lib/server/queries";
import type { CalendarConnection, CalendarProviderStatus, Me } from "@/types/api";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

/** Calendar data is optional here: an outage shows in its card, not the page. */
async function loadCalendar(): Promise<{
  providers: CalendarProviderStatus[] | null;
  connections: CalendarConnection[] | null;
}> {
  try {
    const [providers, connections] = await Promise.all([
      getCalendarProviders(),
      getCalendarConnections(),
    ]);
    return { providers, connections };
  } catch (error) {
    if (error instanceof ApiError && error.kind === "unauthorized") throw error;
    return { providers: null, connections: null };
  }
}

function single(value: string | string[] | undefined): string | null {
  return typeof value === "string" ? value : null;
}

async function SettingsBoundary({ searchParams }: { searchParams: SearchParams }) {
  let me: Me;
  let calendar: Awaited<ReturnType<typeof loadCalendar>>;
  const parameters = await searchParams;
  const calendarNotice = single(parameters.calendar) ?? single(parameters.calendar_error);

  try {
    [me, calendar] = await Promise.all([getMe(), loadCalendar()]);
  } catch (error) {
    if (error instanceof ApiError && error.kind === "unavailable") {
      return <UnavailableState />;
    }
    if (error instanceof ApiError) {
      return <ErrorState message={error.message} />;
    }
    throw error;
  }

  return (
    <SettingsView
      me={me}
      calendarProviders={calendar.providers}
      calendarConnections={calendar.connections}
      calendarNotice={calendarNotice}
    />
  );
}

export default function SettingsPage({ searchParams }: { searchParams: SearchParams }) {
  return (
    <Suspense fallback={<LoadingState rows={4} label="Loading your settings" />}>
      <SettingsBoundary searchParams={searchParams} />
    </Suspense>
  );
}
