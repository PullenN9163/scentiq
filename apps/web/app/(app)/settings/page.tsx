import { Suspense } from "react";

import { ErrorState, LoadingState, UnavailableState } from "@/components/shared/states";
import { SettingsView } from "@/features/settings/settings-view";
import { ApiError } from "@/lib/server/api-client";
import { getMe } from "@/lib/server/queries";
import type { Me } from "@/types/api";

async function SettingsBoundary() {
  let me: Me;

  try {
    me = await getMe();
  } catch (error) {
    if (error instanceof ApiError && error.kind === "unavailable") {
      return <UnavailableState />;
    }
    if (error instanceof ApiError) {
      return <ErrorState message={error.message} />;
    }
    throw error;
  }

  return <SettingsView me={me} />;
}

export default function SettingsPage() {
  return (
    <Suspense fallback={<LoadingState rows={4} label="Loading your settings" />}>
      <SettingsBoundary />
    </Suspense>
  );
}
