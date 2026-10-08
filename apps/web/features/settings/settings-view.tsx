"use client";

import { Lock, MapPin, SlidersHorizontal, UserRound } from "lucide-react";
import { useActionState } from "react";

import { ApiStatus } from "@/components/api-status";
import { Field, FormMessage } from "@/components/shared/form-field";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { CalendarConnectionsCard } from "@/features/settings/calendar-connections";
import { DeleteAccountPanel } from "@/features/settings/delete-account-panel";
import { idleState } from "@/lib/action-state";
import { updatePreferences, updateProfile } from "@/lib/server/actions";
import type { CalendarConnection, CalendarProviderStatus, Me } from "@/types/api";

/**
 * Persisted profile, preferences, forecast location, and calendar connections.
 * Notification delivery is represented by a roadmap note.
 */
export function SettingsView({
  me,
  calendarProviders = null,
  calendarConnections = null,
  calendarNotice = null,
}: {
  me: Me;
  /** Null when the calendar service could not be reached. */
  calendarProviders?: CalendarProviderStatus[] | null;
  calendarConnections?: CalendarConnection[] | null;
  calendarNotice?: string | null;
}) {
  const [profileState, profileAction, profilePending] = useActionState(updateProfile, idleState);
  const [preferenceState, preferenceAction, preferencePending] = useActionState(
    updatePreferences,
    idleState,
  );

  const preferences = me.preferences;

  return (
    <section className="page">
      <PageHeader
        eyebrow="Make it yours"
        title="Settings"
        description="Your profile and recommendation preferences, saved to your account."
      />

      <div className="settings-grid">
        <Card>
          <CardContent>
            <div className="settings-title">
              <UserRound size={19} />
              <h2>Profile</h2>
            </div>
            <form className="stack" action={profileAction} noValidate>
              <FormMessage state={profileState} />
              <Field
                name="display_name"
                label="Display name"
                state={profileState}
                fallbackValue={me.display_name}
              >
                {(props) => <Input type="text" maxLength={120} {...props} />}
              </Field>
              <div className="field">
                <span className="label">Email</span>
                <Input value={me.email} readOnly aria-readonly="true" />
                <span className="field-hint">
                  Your email comes from your sign-in provider and cannot be changed here.
                </span>
              </div>
              <Button type="submit" disabled={profilePending}>
                {profilePending ? "Saving…" : "Save profile"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <div className="settings-title">
              <SlidersHorizontal size={19} />
              <h2>Recommendation preferences</h2>
            </div>
            <form className="stack" action={preferenceAction} noValidate>
              <FormMessage state={preferenceState} />
              <Field
                name="location"
                label="Location"
                state={preferenceState}
                fallbackValue={preferences.location ?? ""}
                hint='A city, optionally with its country, e.g. "Leeds, UK". Drives your forecast.'
              >
                {(props) => <Input type="text" maxLength={120} {...props} />}
              </Field>
              <Field
                name="temperature_unit"
                label="Temperature unit"
                state={preferenceState}
                fallbackValue={preferences.temperature_unit ?? ""}
              >
                {(props) => (
                  <select className="select" {...props}>
                    <option value="">Default (°F)</option>
                    <option value="fahrenheit">Fahrenheit (°F)</option>
                    <option value="celsius">Celsius (°C)</option>
                  </select>
                )}
              </Field>
              <Field
                name="preferred_season"
                label="Preferred season"
                state={preferenceState}
                fallbackValue={preferences.preferred_season ?? ""}
              >
                {(props) => (
                  <select className="select" {...props}>
                    <option value="">No preference</option>
                    <option value="spring">Spring</option>
                    <option value="summer">Summer</option>
                    <option value="fall">Fall</option>
                    <option value="winter">Winter</option>
                  </select>
                )}
              </Field>
              <Field
                name="preferred_occasion"
                label="Preferred occasion"
                state={preferenceState}
                fallbackValue={preferences.preferred_occasion ?? ""}
              >
                {(props) => (
                  <select className="select" {...props}>
                    <option value="">No preference</option>
                    <option value="work">Work</option>
                    <option value="casual">Casual</option>
                    <option value="date">Date</option>
                    <option value="dinner">Dinner</option>
                    <option value="party">Party</option>
                    <option value="formal">Formal</option>
                    <option value="gym">Gym</option>
                    <option value="travel">Travel</option>
                    <option value="other">Other</option>
                  </select>
                )}
              </Field>
              <Field
                name="preferred_projection"
                label="Projection preference"
                state={preferenceState}
                fallbackValue={preferences.preferred_projection ?? ""}
              >
                {(props) => (
                  <select className="select" {...props}>
                    <option value="">No preference</option>
                    <option value="intimate">Intimate</option>
                    <option value="moderate">Moderate</option>
                    <option value="strong">Strong</option>
                  </select>
                )}
              </Field>
              <Field
                name="preferred_longevity"
                label="Longevity preference (0–10)"
                state={preferenceState}
                fallbackValue={preferences.preferred_longevity?.toString() ?? ""}
              >
                {(props) => <Input type="number" min="0" max="10" step="0.1" {...props} />}
              </Field>
              <Field
                name="maximum_sprays"
                label="Maximum sprays"
                state={preferenceState}
                fallbackValue={preferences.maximum_sprays?.toString() ?? ""}
              >
                {(props) => <Input type="number" min="1" max="20" step="1" {...props} />}
              </Field>
              <p className="field-hint">
                Saving replaces the whole set, so anything you clear is removed.
              </p>
              <Button type="submit" disabled={preferencePending}>
                {preferencePending ? "Saving…" : "Save preferences"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <div className="settings-title">
              <MapPin size={19} />
              <h2>Weather</h2>
            </div>
            {preferences.location === null ? (
              <p className="muted">
                Add a location under Recommendation preferences to see forecasts on Today.
              </p>
            ) : preferences.location_label ? (
              <>
                <p>
                  Forecasts are for <strong>{preferences.location_label}</strong>
                  {preferences.timezone ? ` (${preferences.timezone})` : ""}.
                </p>
                <p className="field-hint">
                  Forecast data by{" "}
                  <a href="https://open-meteo.com/" rel="noreferrer" target="_blank">
                    Open-Meteo
                  </a>
                  .
                </p>
              </>
            ) : (
              <p className="muted">
                We haven&apos;t matched &ldquo;{preferences.location}&rdquo; to a place yet. It will
                be looked up again the next time a forecast loads.
              </p>
            )}
          </CardContent>
        </Card>

        <CalendarConnectionsCard
          providers={calendarProviders}
          connections={calendarConnections}
          notice={calendarNotice}
        />

        <Card><CardContent><h2>Notifications</h2><p className="muted">Morning recommendations and weekly reminders are on the roadmap.</p></CardContent></Card>

        <Card>
          <CardContent>
            <div className="settings-title">
              <Lock size={19} />
              <h2>Your account</h2>
            </div>
            <p className="muted">
              Your collection, wear history, preferences and custom fragrances are stored against
              your account. Deleting it removes all of them.
            </p>
            <DeleteAccountPanel />
          </CardContent>
        </Card>

        <Card className="settings-system">
          <CardContent>
            <p className="eyebrow">System</p>
            <h2>API availability</h2>
            <ApiStatus />
            <p className="muted">Same-origin service health.</p>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
