# Personalized recommendation intelligence

ScentIQ shares a member taste profile across Today, My Week, discovery, layering, and Ask ScentIQ. Candidate eligibility and application guidance remain backend responsibilities. Optional Azure inference compares bounded candidates; unavailable inference returns personalized baseline results.

## Taste and eligibility

Settings accepts liked and disliked notes, accords, and families, a variety preference, and explicit fragrance exclusions. Entries use normalized catalog slugs. Personal collection ratings, wear ratings, and layering ratings supply learned feature affinity. Explicit feature preferences override learned affinity. Duplicate bottles contribute one average collection rating. Unrated ownership is weak evidence rather than a positive rating.

The derived profile is versioned from its features, exclusions, and variety preference. Its cache can be recreated from member data and is removed with the account. Discovery compares positive taste evidence while retaining collection redundancy information. Layering selects bounded anchors by affinity before generating valid combinations.

“Not today” is neutral taste feedback. “Too strong” reduces the next wear application starting point without disliking the fragrance. “Dislike this scent” excludes that fragrance from future recommendations and contributes negative taste evidence. These controls are distinct from browsing another option.

## Context and planning

The context builder resolves local time and hemisphere season from the saved location. Today uses the current hour unless an active or upcoming event supplies a target window; future open days use 09:00 local time. Ongoing and overnight events use the remaining event window. Logical all-day dates are preserved across timezones.

Hourly weather is stored alongside daily snapshots using UTC timestamps, including repeated daylight-saving hours. Event windows aggregate temperature, humidity, precipitation, and condition. Responses disclose hourly/daily/unavailable resolution and stale forecasts. Daily data remains the fallback when hourly coverage is missing. Missing metadata remains neutral evidence, not a fabricated measurement. Weather relationships are recommendation heuristics, not guarantees of fragrance performance.

Calendar members can correct occasion, formality, and setting. Corrections survive synchronization. By default titles are classified with local keywords and only structured context reaches recommendation inference. Separate Settings consent permits interpreting ambiguous titles through the bounded inference provider. Hidden events, unchanged titles, and member corrections are excluded from interpretation; each sync request permits at most two interpretations.

My Week applies planned-use penalties sequentially across contexts, scaled by the member’s variety setting. Eligible accepted choices remain locked. Wearing, selling, or excluding a selected fragrance allows a new applicable result. Small collections may require repeats, which the plan discloses.

## Stable choices and versioning

Wear batches persist all distinct eligible fragrance candidates. Explicit next requests use row locks, idempotency receipts, and the expected displayed fragrance to avoid duplicate advances. Reloads retain the selected candidate. Accepted alternatives are recorded as seen. Exhaustion requires an explicit reset.

Discovery and layering use member-scoped batches of up to 50 candidates, with canonical unordered stack keys. Their fingerprints include parameters, profile, collection state, local context/weather, model configuration, catalog import version, and private fragrance changes. Changed inputs invalidate stale batches. Responses include remaining-option status; stale requests instruct the client to refresh.

Interactive discovery and portable worker discovery share scoring functions. Worker inputs carry versioned taste features and exclusions, without member identity. A snapshot from a different taste profile is bypassed in favor of current scoring. AI-enabled discovery uses the current ranking path instead of a baseline worker snapshot.

## Optional Azure ranking

The five surface flags and shadow mode default off. The ranker submits at most 12 candidates and a bounded structured context, validates returned candidate IDs and evidence references, and preserves backend eligibility and spray guidance. Fit scores and evidence coverage remain baseline indicators, not AI probabilities. Shadow mode records top-choice differences while delivering the baseline ordering.

Inference has a ten-second ranking HTTP timeout. A durable member-scoped cache claims an input before dispatch, preventing concurrent identical inference. Failed or ambiguous calls retain their maximum reserved charge and return the baseline. The cache key includes candidate inputs, context, profile, prompt, deployment, and surface configuration.

All inference, including advisor turns and optional title interpretation, shares an atomic monthly UTC ledger capped at $25. Integer microdollar reservations precede dispatch; complete usage settles them exactly once. Conservative configurable token price ceilings must cover the deployed model’s actual rates. Application accounting does not cap unrelated Azure consumption or replace Azure billing controls.

See the [Azure deployment runbook](../runbooks/azure-deployment.md) for configuration, the budgeted synthetic smoke test, shadow rollout, and alerts. Model availability, quota, and managed-identity access must be verified before activation. Quality activation additionally requires a reviewed comparison against the baseline; passing deterministic tests alone does not establish AI preference quality.
