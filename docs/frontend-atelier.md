# Atelier interface

Atelier is the redesigned interface for ScentIQ. Its one idea is that the scent supplies the color: the interface stays warm and neutral, and each fragrance brings a color from its dominant accord. Atelier is available in light and dark appearances, and it is turned on with a single configuration value. The existing interface remains the default and is unchanged while the flag is off.

## Turning Atelier on

Set `SCENTIQ_ATELIER_UI_ENABLED` to `true` (any letter case) in the web app's environment. Any other value, or no value, keeps the current interface.

The flag is read on the server with `isAtelierEnabled()` in `lib/atelier-flag.ts`. When it is on:

- The root layout sets `data-atelier="true"` on `<html>`. The Atelier tokens apply only under that attribute.
- The public landing page, sign-in and sign-up pages render their Atelier versions.
- The signed-in pages render the Atelier shell and the Atelier views.
- Clerk's appearance uses the Atelier values in `features/auth/clerk-appearance.ts`.

Each signed-in page checks the flag on its own, so a page that has not been converted keeps the existing view.

## Tokens

Atelier tokens are defined in two files under `apps/web/app/`:

- `atelier.css` holds the color, shadow, spacing, radius and font-family tokens. Light values sit on `html[data-atelier]`. Dark values apply to `html[data-atelier][data-theme="dark"]` and to any nested element with `data-theme="dark"`. The Blend studio and the closing band of the landing page use the nested form to stay dark in either appearance.
- `atelier-base.css` holds the base page styles, the type scale (`at-display-xl`, `at-title`, `at-body`, `at-overline` and the other `at-` classes), the page gutter, focus rings and the reduced-motion rules.

The two type faces, Fraunces for display and Figtree for text, load through `next/font` in the root layout with `display: swap`. Only the weights the type scale uses are loaded.

Components use the tokens by name, for example `var(--ink)`, `var(--surface)` and `var(--accord-woody-field)`. Do not hard-code colors in Atelier components.

## Components

Shared Atelier components live in `apps/web/components/atelier/`. Import them from `@/components/atelier`:

- `Plate` shows a bottle photo on a light plate tinted with the fragrance's accord color. The photo uses multiply blending, so it reads the same in both appearances. Without a photo, the plate shows the house name.
- `FragranceCard` and `FragranceRow` present a fragrance in a grid or a list. Every fragrance in the interface uses one of these two.
- `Button`, `Chip`, `SegmentedControl`, `Field`, `TextInput`, `Select`, `Stepper`, `Switch` and `TextArea` are the controls.
- `Sheet` is the one bottom sheet, dialog or side panel. It moves between a bottom sheet on phones, a centered sheet on tablets and a side panel on desktop. It traps focus, closes on Escape and returns focus to the element that opened it.
- `Vial` shows a saved blend and is reused by the Collection and the Blend studio.
- `AccordStrip` shows the accord mix of a fragrance or collection.
- `AtelierEmpty`, `AtelierError` and `AtelierUnavailable` are the empty, error and unavailable states.
- `AtelierToaster` shows short confirmations.

The shell lives in `apps/web/components/atelier-shell/`. It renders the top bar on tablet and desktop, the floating dock on phones, the account menu and the Ask field. The Blend studio uses a studio mode with no top bar or dock.

## Accord mapping

`apps/web/lib/accord.ts` turns a fragrance into one of eleven accord keys: woody, fresh, amber, floral, green, citrus, spicy, musk, gourmand, aquatic and neutral.

- `accordFor(fragrance)` reads the first of the fragrance's top accords. If there is none, it reads the olfactory family. If neither matches, the result is `neutral`.
- `accordFromLabel(label)` matches a single label, case-insensitively, through a keyword table. The table maps words such as "cedar" to woody, "rose" to floral and "vanilla" to gourmand. Labels that match no keyword fall back to `neutral`.
- `accordVars(key)` returns the CSS custom properties for a key: the field color, the deep color and the chart color. Apply it as an inline style on a plate, hero, vial or chart segment.

The keyword table is a starting list and is covered by unit tests in `lib/accord.test.ts`. Add a keyword there when a real accord shows up as neutral.

## Motion

Motion follows a small set of rules:

- Single-element states, such as hover, pressed and focus, use CSS transitions.
- Exit animations, shared-element transitions, drags and springs use Motion. Motion tokens live in `apps/web/lib/motion.ts`.
- Signature motion appears in three places only: the Blend studio (mist, liquid and bloom), the moment a wear is logged, and the new pick on Today. The Today bloom opens the accord color outward from the bottle over about 600 milliseconds. It plays once when the day's first pick appears and again whenever "Not today" or "Not for me" brings a new pick.
- Reduced motion is honored everywhere. With the system setting for reduced motion, or with the "Reduce effects" setting turned on in Settings, movement, mist, liquid and bloom are removed and content appears in place. `effectsReduced()` in `components/atelier/mist.ts` checks both.

## Layout

- Phones (under 700px) use a header with the wordmark, Ask and the account menu, and a floating dock at the bottom. Content keeps clear of the dock.
- Tablets in portrait (700 to 1099px) use a top bar, and Ask is a button. Sheets are centered.
- Tablets in landscape and desktops (1100px and up) use a top bar with the Ask field. The fragrance sheet is a right-hand panel.
- Fragrance grids use `repeat(auto-fill, minmax(168px, 1fr))`, so the column count follows the width.
- Interactive controls are at least 44 by 44 pixels. Every control is reachable by keyboard, and focus is shown with a 2 pixel accent ring.

## Fixture views

The fixture server renders Atelier views with stub data and no sign-in. Start it from `apps/web`:

```sh
node e2e/fixtures/server.mjs
```

It serves `http://127.0.0.1:3100/?view=<name>&theme=<light|dark>`. Atelier views are:

| View | Screen |
| --- | --- |
| `landing-atelier` | Public landing page |
| `sign-in-atelier`, `sign-up-atelier` | Sign-in and sign-up layout (the Clerk form is replaced by a stub) |
| `today-atelier`, `today-loading` | Today, with its loading state |
| `week-atelier` | Week |
| `collection-atelier`, `blends` | Collection, and its Blends segment |
| `discover-atelier`, `discover-atelier-error`, `discover-loading` | Discover, with its error and loading states |
| `insights-atelier` | Your taste |
| `settings-atelier` | Settings |
| `fragrance` | The fragrance sheet and full page |
| `sheet` | Sheet primitives |
| `ask` | Ask |
| `blend` | Blend studio. Options: `few`, `empty`, `error`, `nosaved`, `a=`, `stack=`, `saved=`, `mode=`, `goal=` |
| `primitives` | Component gallery |

Add `shell=atelier` to any page view to render it inside the Atelier shell.

## Verification

Run these from the repository root before merging Atelier changes:

```sh
pnpm lint:web
pnpm typecheck:web
pnpm test:web
pnpm build
```

The visual suite in `apps/web/e2e/atelier.spec.ts` checks each Atelier view at 390, 820, 1180 and 1440 pixels in both appearances. It confirms that the page does not scroll horizontally, that the Atelier tokens are active and that no page error occurs. It also takes baseline screenshots of the main screens. Run it with the visual configuration:

```sh
pnpm --filter @scentiq/web test:visual --update-snapshots
pnpm --filter @scentiq/web test:visual
```

As with the other visual suites, baselines are local verification artifacts and are not committed.
