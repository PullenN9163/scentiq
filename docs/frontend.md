# Frontend appearance and browser verification

ScentIQ uses shared semantic surface, foreground, border and accent tokens for its light and dark appearances. The system appearance follows the device setting; an explicit choice persists in the `scentiq-theme` cookie. The root layout initializes the resolved appearance before content paints.

Use paired surface and foreground tokens for new components. Feature styles should stay scoped to their component or feature. Recommendation hero and compact cards share a layout contract and readable badges in both appearances. Ambient backgrounds and spatial transitions stop when the device requests reduced motion.

Numeric sliders pair a keyboard-accessible native range control with a numeric field. Only the numeric field submits a form value. Empty optional values remain empty, and typed values are validated against the original field constraints. A visible slider range does not introduce a new limit on previously unbounded bottle amounts.

## Verification commands

Run from the repository root:

```sh
pnpm test:web
pnpm lint:web
pnpm typecheck:web
pnpm build
```

The isolated visual harness renders the shipped React views with fixed catalog fixtures and service doubles. It covers public and signed-in surfaces at mobile, tablet and desktop widths in both appearances, plus layout containment, recommendation contrast, keyboard controls, focus restoration, reduced motion and recoverable request failures. Its authentication doubles are confined to the fixture server; production authentication is unchanged.

Set `SCENTIQ_VISUAL_ARTIFACTS` to a private directory outside the checkout for screenshots, baselines, traces and results. Create and inspect the first baseline, then compare subsequent runs:

```sh
pnpm --filter @scentiq/web test:visual --update-snapshots
pnpm --filter @scentiq/web test:visual
```

Visual baselines are local verification artifacts and are not committed. A fresh checkout must initialize them before comparison. Authentication-provider fixtures verify surrounding layout; the deployed journey verifies the actual Clerk flow.

Run the separate authenticated journey with an authorized development test identity and the existing Clerk testing configuration. Use `E2E_BASE_URL` for development deployment checks. These tests create test collection entries and wear logs.

## Discover request handling

Discovery scoring has a bounded 60-second read deadline; ordinary API reads retain their 10-second deadline. Catalog search remains available while discovery loads and after a recommendation failure. Collection-status failures disable wishlist writes until status can be reloaded. Authentication and authorization failures are not converted into empty recommendations.

Optional-read diagnostics include failure category, status, error code and a request identifier when supplied by the API. They exclude member data and query text. Correlate these diagnostics with API request durations when investigating latency.

Wear timestamps are resolved to explicit UTC instants in the member's browser before submission, so server timezone differences cannot shift the recorded wear time.
