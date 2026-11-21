"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useActionState, useEffect, useId, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { toast } from "sonner";

import { Button } from "@/components/atelier/button";
import { ChipPicker, parseList } from "@/components/atelier/chip-picker";
import { Field, Stepper, Switch, TextInput } from "@/components/atelier/field";
import { SegmentedControl } from "@/components/atelier/segmented-control";
import { Sheet } from "@/components/atelier/sheet";
import { useThemePreference, type ThemePreference } from "@/components/ui/theme-provider";
import { CalendarConnectionsCard } from "@/features/settings/calendar-connections";
import { DeleteAccountPanel } from "@/features/settings/delete-account-panel";
import { ACCORD_KEYS, ACCORD_LABELS } from "@/lib/accord";
import { idleState, type ActionState } from "@/lib/action-state";
import { readReduceEffects, setReduceEffects } from "@/lib/effects";
import { COMMON_NOTES } from "@/lib/notes";
import { cn } from "@/lib/utils";
import { updatePreferences, updateProfile } from "@/lib/server/actions";
import type { CalendarConnection, CalendarProviderStatus, Me } from "@/types/api";

import { PREFERENCE_FIELDS, preferenceValues, type PreferenceField } from "./preference-values";
import styles from "./settings-atelier.module.css";
import { SECTIONS, sectionFrom, type SectionId } from "./sections";

const FAMILIES = ACCORD_KEYS.filter((key) => key !== "neutral").map((key) => ACCORD_LABELS[key]);
const noSubscription = () => () => {};
const SECTION_EVENT = "scentiq:settings-section";
/** Once the member picks or leaves a section, the server-provided starting section no longer applies. */
let moved = false;
function goTo() {
  moved = true;
  window.dispatchEvent(new Event(SECTION_EVENT));
}
function subscribeLocation(onChange: () => void) {
  window.addEventListener("popstate", onChange);
  window.addEventListener("hashchange", onChange);
  window.addEventListener(SECTION_EVENT, onChange);
  return () => { window.removeEventListener("popstate", onChange); window.removeEventListener("hashchange", onChange); window.removeEventListener(SECTION_EVENT, onChange); };
}

function isPhone() {
  return typeof window !== "undefined" && (window.matchMedia?.("(max-width: 699px)").matches ?? false);
}

/** Saving status for one section; a toast too on phones, where the caption may be off screen. */
function useSectionResult(state: ActionState, pending: boolean) {
  useEffect(() => {
    if (state.status === "success" && isPhone()) toast.success(state.message ?? "Saved");
  }, [state]);
  return pending || state.status === "idle" ? null : state;
}

function SaveRow({ label, pending, result }: { label: string; pending: boolean; result: ActionState | null }) {
  return (
    <div className={styles.saveRow}>
      <Button type="submit" disabled={pending}>{pending ? "Saving…" : `Save ${label.toLowerCase()}`}</Button>
      {!pending && result?.status === "success" ? <span className="at-caption" role="status">Saved just now</span> : null}
      {!pending && result?.status === "error" ? <p className={styles.error} role="alert">{result.message ?? "Check the highlighted fields."}</p> : null}
    </div>
  );
}

/** Every preference this section does not show, as hidden inputs, so saving keeps them. */
function KeepOthers({ values, own }: { values: Record<PreferenceField, string | null>; own: readonly PreferenceField[] }) {
  return (
    <>
      {PREFERENCE_FIELDS.filter((field) => !own.includes(field)).map((field) => (values[field] === null ? null : <input key={field} type="hidden" name={field} value={values[field] ?? ""} />))}
    </>
  );
}

function SegmentField({ label, name, value, onChange, options }: { label: string; name: string; value: string; onChange: (value: string) => void; options: [string, string][] }) {
  return (
    <div className={styles.segmentField}>
      <span className={styles.fieldLabel}>{label}</span>
      <input type="hidden" name={name} value={value} />
      <SegmentedControl label={label} value={value} onChange={onChange} segments={options.map(([option, text]) => ({ value: option, label: text }))} className={styles.segments} />
    </div>
  );
}

export function SettingsAtelier({
  me,
  calendarProviders = null,
  calendarConnections = null,
  calendarNotice = null,
  initialSection = null,
}: {
  me: Me;
  calendarProviders?: CalendarProviderStatus[] | null;
  calendarConnections?: CalendarConnection[] | null;
  calendarNotice?: string | null;
  initialSection?: SectionId | null;
}) {
  const chosen = useSyncExternalStore(subscribeLocation, () => sectionFrom(window.location.search, window.location.hash) ?? (moved ? null : initialSection), () => initialSection);
  const selected = chosen ?? "profile";

  function open(id: SectionId) {
    window.history.pushState(window.history.state, "", `/settings?section=${id}#${id}`);

    goTo();
  }
  function back() {
    window.history.pushState(window.history.state, "", "/settings");

    goTo();
  }

  const current = SECTIONS.find((section) => section.id === selected)!;

  return (
    <div className="at-page">
      <div className={styles.layout} data-open={chosen ? "true" : "false"}>
        <nav className={styles.list} aria-label="Settings sections">
          <h1 className={styles.title}>Settings</h1>
          <ul>
            {SECTIONS.map((section) => (
              <li key={section.id}>
                <button type="button" className={cn(styles.listItem, section.id === selected && styles.listSelected)} aria-current={section.id === selected ? "page" : undefined} onClick={() => open(section.id)}>
                  {section.label}
                  <ChevronRight aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
        </nav>
        <section className={styles.detail} aria-labelledby="settings-section-title" id={selected}>
          <button type="button" className={styles.back} onClick={back}><ChevronLeft aria-hidden="true" />Settings</button>
          <h2 id="settings-section-title" className="at-title">{current.label}</h2>
          {selected === "profile" ? <ProfileSection me={me} /> : null}
          {selected === "taste" ? <TasteSection me={me} /> : null}
          {selected === "place" ? <PlaceSection me={me} /> : null}
          {selected === "calendar" ? <CalendarSection me={me} providers={calendarProviders} connections={calendarConnections} notice={calendarNotice} /> : null}
          {selected === "appearance" ? <AppearanceSection /> : null}
          {selected === "account" ? <AccountSection me={me} /> : null}
        </section>
      </div>
    </div>
  );
}

function ProfileSection({ me }: { me: Me }) {
  const id = useId();
  const [state, action, pending] = useActionState(updateProfile, idleState);
  const result = useSectionResult(state, pending);
  return (
    <form action={action} className={styles.form} noValidate>
      <Field label="Display name" htmlFor={`${id}-name`} error={state.fieldErrors?.display_name}>
        <TextInput id={`${id}-name`} name="display_name" maxLength={120} defaultValue={state.values?.display_name ?? me.display_name} invalid={Boolean(state.fieldErrors?.display_name)} />
      </Field>
      <div className={styles.readOnly}><span className={styles.fieldLabel}>Email</span><span>{me.email}</span></div>
      <SaveRow label="Profile" pending={pending} result={result} />
    </form>
  );
}

const TASTE_FIELDS: PreferenceField[] = ["liked_notes", "disliked_notes", "liked_accords", "disliked_accords", "liked_families", "disliked_families", "variety_preference", "maximum_sprays", "preferred_season", "preferred_occasion", "preferred_projection", "preferred_longevity"];

function TasteSection({ me }: { me: Me }) {
  const id = useId();
  const [state, action, pending] = useActionState(updatePreferences, idleState);
  const result = useSectionResult(state, pending);
  const values = preferenceValues(me.preferences);
  const value = (field: PreferenceField) => state.values?.[field] ?? values[field] ?? "";
  const [variety, setVariety] = useState(value("variety_preference") || "balanced");
  const [sprays, setSprays] = useState<number>(Number(value("maximum_sprays")) || Number.NaN);
  const [season, setSeason] = useState(value("preferred_season"));
  const [occasion, setOccasion] = useState(value("preferred_occasion"));
  const [projection, setProjection] = useState(value("preferred_projection"));
  return (
    <form action={action} className={styles.form} noValidate>
      <KeepOthers values={values} own={TASTE_FIELDS} />
      {(["notes", "accords", "families"] as const).map((kind) => (["liked", "disliked"] as const).map((polarity) => {
        const name = `${polarity}_${kind}` as PreferenceField;
        const choices = kind === "notes" ? COMMON_NOTES : FAMILIES;
        return (
          <div key={name}>
            <ChipPicker name={name} label={`${polarity === "liked" ? "Liked" : "Disliked"} ${kind}`} choices={choices} defaultValue={parseList(value(name))} />
            {state.fieldErrors?.[name] ? <p className={styles.error}>{state.fieldErrors[name]}</p> : null}
          </div>
        );
      }))}
      <SegmentField label="How much variety?" name="variety_preference" value={variety} onChange={setVariety} options={[["familiar", "Familiar"], ["balanced", "Balanced"], ["adventurous", "Adventurous"]]} />
      <Field label="Maximum sprays" htmlFor={`${id}-sprays`} error={state.fieldErrors?.maximum_sprays}>
        <Stepper id={`${id}-sprays`} name="maximum_sprays" label="Maximum sprays" min={1} max={20} value={sprays} onChange={setSprays} />
      </Field>
      <SegmentField label="Preferred season" name="preferred_season" value={season} onChange={setSeason} options={[["", "No preference"], ["spring", "Spring"], ["summer", "Summer"], ["fall", "Fall"], ["winter", "Winter"]]} />
      <div className={styles.segmentField}>
        <span className={styles.fieldLabel}>Preferred occasion</span>
        <input type="hidden" name="preferred_occasion" value={occasion} />
        <div className={styles.chips} role="group" aria-label="Preferred occasion">
          {[["", "No preference"], ["work", "Work"], ["casual", "Casual"], ["date", "Date"], ["dinner", "Dinner"], ["party", "Party"], ["formal", "Formal"], ["gym", "Gym"], ["travel", "Travel"], ["other", "Other"]].map(([option, text]) => (
            <button key={option || "none"} type="button" className={cn(styles.choice, occasion === option && styles.choiceOn)} aria-pressed={occasion === option} onClick={() => setOccasion(option)}>{text}</button>
          ))}
        </div>
      </div>
      <SegmentField label="Projection" name="preferred_projection" value={projection} onChange={setProjection} options={[["", "No preference"], ["intimate", "Intimate"], ["moderate", "Moderate"], ["strong", "Strong"]]} />
      <Field label="Longevity (0 to 10)" htmlFor={`${id}-longevity`} error={state.fieldErrors?.preferred_longevity}>
        <TextInput id={`${id}-longevity`} name="preferred_longevity" type="number" min={0} max={10} step={0.1} defaultValue={value("preferred_longevity")} className={styles.short} />
      </Field>
      <SaveRow label="Taste" pending={pending} result={result} />
    </form>
  );
}

const PLACE_FIELDS: PreferenceField[] = ["location", "temperature_unit"];

function PlaceSection({ me }: { me: Me }) {
  const id = useId();
  const [state, action, pending] = useActionState(updatePreferences, idleState);
  const result = useSectionResult(state, pending);
  const values = preferenceValues(me.preferences);
  const [unit, setUnit] = useState(state.values?.temperature_unit ?? values.temperature_unit ?? "");
  const { location_label: label, timezone } = me.preferences;
  return (
    <form action={action} className={styles.form} noValidate>
      <KeepOthers values={values} own={PLACE_FIELDS} />
      <Field label="Location" htmlFor={`${id}-location`} hint='A city, optionally with its country, such as "Leeds, UK".' error={state.fieldErrors?.location}>
        <TextInput id={`${id}-location`} name="location" maxLength={120} defaultValue={state.values?.location ?? values.location ?? ""} />
      </Field>
      <SegmentField label="Temperature" name="temperature_unit" value={unit} onChange={setUnit} options={[["fahrenheit", "Fahrenheit"], ["celsius", "Celsius"]]} />
      <p className="at-caption">
        {label ? `Forecasts are for ${label}${timezone ? ` (${timezone})` : ""}. ` : me.preferences.location ? `"${me.preferences.location}" has not been matched to a place yet. ` : ""}
        Forecast data by <a className="at-link" href="https://open-meteo.com/" rel="noreferrer" target="_blank">Open-Meteo</a>.
      </p>
      <SaveRow label="Place" pending={pending} result={result} />
    </form>
  );
}

function CalendarSection({ me, providers, connections, notice }: { me: Me; providers: CalendarProviderStatus[] | null; connections: CalendarConnection[] | null; notice: string | null }) {
  const [state, action, pending] = useActionState(updatePreferences, idleState);
  const values = preferenceValues(me.preferences);
  const [enabled, setEnabled] = useState(Boolean(me.preferences.calendar_ai_titles_enabled));
  const form = useRef<HTMLFormElement>(null);
  return (
    <div className={styles.form}>
      <div className="atelier-legacy-form">
        <CalendarConnectionsCard providers={providers} connections={connections} notice={notice} />
      </div>
      <form ref={form} action={action} className={styles.switchRow}>
        <KeepOthers values={values} own={["calendar_ai_titles_enabled"]} />
        {enabled ? <input type="hidden" name="calendar_ai_titles_enabled" value="on" /> : null}
        <div>
          <span className={styles.fieldLabel}>Interpret event titles</span>
          <p className="at-caption">Allow AI to interpret titles from your selected calendars. Hidden events stay excluded; descriptions and attendees are never sent.</p>
          {state.status === "error" ? <p className={styles.error} role="alert">{state.message ?? "That did not save. Try again."}</p> : null}
        </div>
        <Switch label="Interpret event titles" checked={enabled} disabled={pending} onCheckedChange={(next) => { setEnabled(next); queueMicrotask(() => form.current?.requestSubmit()); }} />
      </form>
    </div>
  );
}

function AppearanceSection() {
  const router = useRouter();
  const { preference, setPreference } = useThemePreference();
  const stored = useSyncExternalStore(noSubscription, readReduceEffects, () => false);
  const [reduced, setReduced] = useState<boolean | null>(null);
  const on = reduced ?? stored;
  return (
    <div className={styles.form}>
      <div className={styles.segmentField}>
        <span className={styles.fieldLabel}>Theme</span>
        <SegmentedControl<ThemePreference> label="Theme" value={preference} onChange={setPreference} segments={[{ value: "system", label: "System" }, { value: "light", label: "Light" }, { value: "dark", label: "Dark" }]} />
      </div>
      <div className={styles.switchRow}>
        <div>
          <span className={styles.fieldLabel}>Reduce effects</span>
          <p className="at-caption">Replaces mist, liquid and color blooms with simple fades.</p>
        </div>
        <Switch label="Reduce effects" checked={on} onCheckedChange={(next) => { setReduced(next); setReduceEffects(next); router.refresh(); }} />
      </div>
    </div>
  );
}

function AccountSection({ me }: { me: Me }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={styles.form}>
      <div className={styles.readOnly}><span className={styles.fieldLabel}>Email</span><span>{me.email}</span></div>
      <p className="at-caption">Your collection, wear history, preferences and custom fragrances are stored against your account. Deleting it removes all of them.</p>
      <div><Button variant="text" className={styles.danger} onClick={() => setOpen(true)}>Delete my account</Button></div>
      <Sheet open={open} onOpenChange={setOpen} title="Delete your account?">
        <div className="atelier-legacy-form"><DeleteAccountPanel startConfirming onCancel={() => setOpen(false)} /></div>
      </Sheet>
    </div>
  );
}

export function SettingsSkeleton({ children }: { children?: ReactNode }) {
  return (
    <div className="at-page" aria-busy="true">
      <span className="sr-only" role="status">Loading your settings</span>
      <span className="at-skeleton" style={{ width: 200, height: 48, marginBottom: 24 }} />
      <div style={{ display: "grid", gap: 12, maxWidth: 520 }}>{[0, 1, 2, 3].map((index) => <span key={index} className="at-skeleton" style={{ height: 48 }} />)}</div>
      {children}
    </div>
  );
}
