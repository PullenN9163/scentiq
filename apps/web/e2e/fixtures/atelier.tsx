// Atelier fixture views. Rendered by main.tsx with deterministic stub data.
import {useState, type ReactNode} from "react";
import {Button, Chip, FragranceCard, FragranceRow, Plate, Sheet} from "@/components/atelier";
import {accordFor} from "@/lib/accord";
import {toast} from "sonner";
import type {FragranceSummary, Me, Occasion, WearLogEntry} from "@/types/api";
import type {WearPlan, WearRecommendation} from "@/types/wear-intelligence";
import type {WeatherResult} from "@/lib/weather";
import type {CalendarResult} from "@/lib/calendar";
import {collectionInsights} from "@/test/catalog-fixtures";
import {TodaySkeleton, TodayView} from "@/features/today/today-view";
import {WeekGlance} from "@/features/today/week-glance";

/** Views that render with the Atelier tokens (data-atelier on the root). */
export const ATELIER_VIEWS = new Set(["primitives"]);

/** Page views rendered inside the Atelier shell. */
export const ATELIER_PAGE_VIEWS = new Set<string>(["today-atelier", "today-loading"]);

/** A stand-in product photo: a bottle on a white studio background. */
export function bottlePhoto(glass = "#e9e2d8", cap = "#2b2622") {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 375 500"><rect width="375" height="500" fill="#ffffff"/><rect x="157" y="92" width="61" height="58" rx="6" fill="${cap}"/><rect x="171" y="146" width="33" height="22" fill="#b9b1a6"/><rect x="112" y="166" width="151" height="250" rx="18" fill="${glass}" stroke="#b9b1a6" stroke-width="3"/><rect x="134" y="250" width="107" height="70" rx="4" fill="#ffffff" opacity=".85"/></svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

/** A varied shelf for Atelier views: different accords, some without photos. */
export function atelierFragrances(base: FragranceSummary[]): FragranceSummary[] {
  const [first] = base;
  const make = (id: string, name: string, house: string, accords: string[], photo: string | null): FragranceSummary => ({...first, id, name, brand: {...first.brand, id: `${id}-house`, name: house}, top_accords: accords, olfactory_family: accords[0] ?? null, image_url: photo});
  return [
    {...base[0], top_accords: ["Musky", "Woody", "Fresh"], image_url: bottlePhoto()},
    make("44444444-4444-4444-8444-444444444444", "By the Fireplace", "Maison Margiela", ["Amber", "Smoky"], bottlePhoto("#c98a4b", "#3b2a1c")),
    make("55555555-5555-4555-8555-555555555555", "Silver Mountain Water", "Creed", ["Fresh", "Citrus"], bottlePhoto("#dfe7ea", "#9aa3a8")),
    make("66666666-6666-4666-8666-666666666666", "MYSLF Le Parfum", "Yves Saint Laurent", ["Floral", "Woody"], bottlePhoto("#f1ece6", "#1d1d1d")),
    {...base[1], top_accords: ["Woody", "Spicy"], image_url: null},
    make("77777777-7777-4777-8777-777777777777", "Dumont Nitro White", "Dumont", [], null),
    {...base[2], top_accords: ["Aquatic", "Woody"], image_url: bottlePhoto("#cfdbe4", "#2c3e50")},
  ].map(fragrance => ({...fragrance, olfactory_family: fragrance.top_accords[0] ?? null}));
}

/** Mirrors the root layout: tokens on, and the two type faces from Google Fonts. */
export function enableAtelier() {
  document.documentElement.dataset.atelier = "true";
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = "https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500&family=Figtree:wght@400;500;600&display=swap";
  document.head.append(link);
  document.documentElement.style.setProperty("--font-fraunces", "\"Fraunces\"");
  document.documentElement.style.setProperty("--font-figtree", "\"Figtree\"");
}

function PrimitivesView({fragrances}: {fragrances: FragranceSummary[]}) {
  const [sheet, setSheet] = useState(false);
  const [pressed, setPressed] = useState(["Woody"]);
  const plate = (fragrance: FragranceSummary) => ({id: fragrance.id, name: fragrance.name, brand: fragrance.brand.name, imageUrl: fragrance.image_url});
  return <main className="at-page" style={{display: "grid", gap: 32}}>
    <h1 className="at-display-lg">Primitives</h1>
    <div style={{display: "flex", gap: 8, flexWrap: "wrap"}}>
      <Button>Wear it</Button><Button variant="soft">Not today</Button><Button variant="text">Not for me</Button><Button variant="outline">Add fragrance</Button><Button variant="danger">Delete</Button><Button size="sm" variant="soft">Plan it</Button><Button disabled>Saving…</Button>
    </div>
    <div style={{display: "flex", gap: 8, flexWrap: "wrap"}}>
      <Chip>45°F cloudy</Chip><Chip variant="note">Cedar</Chip>
      {["Woody", "Fresh", "Amber"].map(label => <Chip key={label} variant="choice" pressed={pressed.includes(label)} onClick={() => setPressed(value => value.includes(label) ? value.filter(item => item !== label) : [...value, label])}>{label}</Chip>)}
    </div>
    <div style={{display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(168px, 1fr))", gap: 20}}>
      {fragrances.map((fragrance, index) => <FragranceCard key={fragrance.id} fragrance={plate(fragrance)} accord={accordFor(fragrance)} href={`/collection/${fragrance.id}`} status={index === 1 ? "Nearly empty" : null} actions={[{label: "Wear it", onSelect: () => toast.success("Wear logged")}, {label: "Layer it", href: `/layering?a=${fragrance.id}`}]}/>)}
    </div>
    <div style={{maxWidth: 480}}>
      {fragrances.map(fragrance => <FragranceRow key={fragrance.id} fragrance={plate(fragrance)} accord={accordFor(fragrance)} caption="Mon · office" href={`/collection/${fragrance.id}`} trailing={<span className="at-caption">41° rain</span>}/>)}
    </div>
    <div style={{display: "flex", gap: 12, flexWrap: "wrap"}}>{fragrances.map(fragrance => <Plate key={fragrance.id} fragrance={plate(fragrance)} accord={accordFor(fragrance)} style={{width: 120, height: 150}}/>)}</div>
    <div><Button variant="outline" onClick={() => setSheet(true)}>Open sheet</Button><Button variant="soft" onClick={() => toast.success("Saved: wore Another 13")}>Show toast</Button></div>
    <Sheet open={sheet} onOpenChange={setSheet} title="Why this" footer={<Button>Done</Button>}><p className="at-body">A clean musk that stays close for a cool, cloudy work day.</p></Sheet>
  </main>;
}

export function atelierView(view: string, fragrances: FragranceSummary[], params: URLSearchParams = new URLSearchParams()): ReactNode | null {
  const shelf = atelierFragrances(fragrances);
  switch (view) {
    case "primitives": return <PrimitivesView fragrances={shelf}/>;
    case "today-atelier": return todayFixture(shelf, params);
    case "today-loading": return <TodaySkeleton/>;
    default: return null;
  }
}

const FIXTURE_DAY = "2026-11-14";
function addDays(date: string, days: number) { const value = new Date(`${date}T12:00:00Z`); value.setUTCDate(value.getUTCDate() + days); return value.toISOString().slice(0, 10); }

export function fixtureRecommendation(fragrance: FragranceSummary, overrides: Partial<WearRecommendation> & {date?: string; daypart?: "day" | "night"; occasion?: Occasion | null} = {}): WearRecommendation {
  const {date = FIXTURE_DAY, daypart = "day", occasion = "work", ...rest} = overrides;
  return {
    id: `rec-${fragrance.id}-${date}-${daypart}`, context_key: `${daypart}:${date}`, recommended_for: `${date}T12:00:00Z`, generation_mode: "baseline", options_exhausted: false, remaining_options: 3, algorithm_version: "wear-v2",
    context: {context_key: `${daypart}:${date}`, recommended_for: `${date}T12:00:00Z`, local_date: date, timezone: "America/New_York", daypart, season: "fall", occasion, high_celsius: 7, condition: "cloudy", source: "day", weather_resolution: "daily", weather_stale: false} as WearRecommendation["context"],
    fragrance, score: 80, evidence_coverage: .7, recommended_sprays: 3, score_components: {occasion: 12.5, weather: 10, season: 15, rotation: 10},
    reasons: ["Clean musk that stays close for a cool, cloudy work day", "Not worn in 12 days", "It fits what you rate highly"], warnings: [], alternatives: [], decision: null,
    ...rest,
  };
}

function todayFixture(shelf: FragranceSummary[], params: URLSearchParams) {
  const me: Me = {id: "fixture-member", display_name: "Alex", email: "alex@example.com", created_at: "2026-10-13T12:00:00Z", lifecycle_state: "active", preferences: {location: "Philadelphia", location_label: "Philadelphia", maximum_sprays: 4, temperature_unit: "fahrenheit", timezone: "America/New_York", preferred_season: null, preferred_occasion: null, preferred_projection: null, preferred_longevity: null}};
  const recs = [fixtureRecommendation(shelf[0], {options_exhausted: params.has("exhausted")})];
  if (!params.has("single")) recs.push(fixtureRecommendation(shelf[1], {daypart: "night", occasion: "dinner", reasons: ["A warmer choice for dinner"]}));
  const plan: WearPlan = {local_date: FIXTURE_DAY, timezone: "America/New_York", gaps: params.has("gaps") ? ["Nothing in your collection suits a formal dinner tonight."] : [], recommendations: params.has("norecs") ? [] : recs};
  const week: WearPlan = {local_date: FIXTURE_DAY, timezone: "America/New_York", gaps: [], recommendations: Array.from({length: 6}, (_, index) => fixtureRecommendation(shelf[(index + 2) % shelf.length], {date: addDays(FIXTURE_DAY, index + 1), occasion: index % 2 ? "work" : null}))};
  const weather: WeatherResult = params.has("nolocation") ? {status: "location_required"} : {status: "ok", forecast: {location_label: "Philadelphia", timezone: "America/New_York", temperature_unit: "fahrenheit", fetched_at: "2026-11-14T08:00:00Z", stale: false, days: [{date: FIXTURE_DAY, condition: "cloudy", high_celsius: 7.2, low_celsius: 2, precipitation_probability: .1, humidity: null}]}};
  const calendar: CalendarResult = params.has("nocal") ? {status: "not_connected"} : {status: "ok", events: [], needsReconnect: params.has("reconnect")};
  const wears: WearLogEntry[] = shelf.slice(3, 6).map((fragrance, index) => ({id: `w${index}`, collection_item_id: `c${index}`, fragrance_id: fragrance.id, fragrance_name: fragrance.name, brand_name: fragrance.brand.name, worn_at: `2026-10-2${2 - index}T14:00:00Z`, sprays: 3, occasion: null, setting: null, notes: null}));
  return <TodayView plan={plan} me={me} insights={collectionInsights({total_items: params.has("empty") ? 0 : 26})} recentWears={wears} weather={weather} calendar={calendar} timeZone="America/New_York" week={<WeekGlance plan={params.has("noweek") ? null : week} today={FIXTURE_DAY} unit="fahrenheit"/>}/>;
}
