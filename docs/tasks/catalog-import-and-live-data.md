# Task brief: import every dataset into the ScentIQ catalog and retire the demo data

## Objective

Load all four raw datasets in `datasets/raw/` into the shared PostgreSQL fragrance catalog as **one de-duplicated catalog**, extend the schema with the attributes the data can actually support, and then switch the frontend from the hard-coded demo catalog in `apps/web/lib/demo` to the real catalog served by the API.

Work in three phases, in this order, and do not start a phase until the previous one passes its checks:

1. **Profile and design** — verify the dataset findings below, settle the attribute list and merge rules, write the migration.
2. **Import** — build an idempotent importer, run it locally, verify counts and de-duplication, then document (and, if credentials are available, run) the Azure dev import.
3. **Frontend** — expose the new data through the API and replace every demo-catalog dependency in `apps/web`.

## Ground rules

- Branch from `dev` as `feat/catalog-import`; open a PR into `dev`. Do **not** push directly to `dev` (every push to `dev` deploys to Azure). Do not touch `main` or the parked `feat/kaggle-dataset-refresh` branch.
- Follow existing conventions: SQLAlchemy 2 typed models in `apps/api/src/scentiq_api/models`, Alembic migrations named `YYYYMMDD_000N_<slug>.py` chained after `20260923_0003`, repositories → services → routers, Pydantic schemas in `schemas/`, conventional commit messages (`feat(catalog): …`).
- The repository privacy check (`scripts/ci/Test-RepositoryPrivacy.ps1`) rejects any tracked path containing `codex`, `chatgpt`, `claude`, `prompt`, `conversation` or `transcript`, and content lines beginning with `user:`, `assistant:`, `system:` or `prompt:`. Name new files and write commit messages accordingly.
- All CI gates must pass before the PR is ready: `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm build`, `pnpm contracts:check`, the API integration tests (`uv run --directory apps/api pytest -m integration` against the compose database), `infra/tests/Test-CompiledInfrastructure.ps1` if infra changes, and the privacy check with `-Scope tracked`.
- Never modify or delete member-owned rows (`owner_user_id IS NOT NULL`) or member data (`user_collection`, `wear_logs`, `wishlists`, etc.). The import only writes shared catalog rows (`owner_user_id IS NULL`).
- Do not invent data. If no source provides a value, store `NULL` / no rows and let the UI say it is unknown. In particular, **no source has occasion data** — leave `fragrance_occasions` empty for imported records.
- Licensing: the Kaggle Fragrantica corpus is **CC BY-NC-SA 4.0** (non-commercial, attribution, share-alike). The provenance/licence of the other three scrapes is undocumented. Add an attribution line in the UI (see Phase 3) and list the licence question as an open item in the PR description.

## Source inventory

Extract the zips first (`datasets/extracted/` is gitignored), or better, have the importer read members straight out of the zips with `zipfile` so it also works with the archive layout the future Kaggle refresh job uploads (`fragrantica-perfumes.zip` containing `perfumes.jsonl`).

| Id | File | Encoding / format | Rows | Record key | Quirks |
|---|---|---|---|---|---|
| `fragrantica` | `fragrantica_full_kaggle.zip` → `perfumes.jsonl` (use this, not the CSV) | UTF-8, one JSON object per line; field reference in `SCHEMA.md` inside the zip | 140,228 | Fragrantica numeric `id` | Git LFS file — run `git lfs pull`. `year` has junk values (min is `20`) — keep only 1700–2100. Names sometimes embed the concentration (`Samsara Eau de Parfum`). Notes are either `tiered` (top/middle/base) **or** `flat`, never both. Vote aggregates go `null` together when absent. |
| `fra_cleaned` | `fragrantica_fra_perfumes.zip` → `fra_cleaned.csv` | **cp1252**, **semicolon**-delimited, **decimal comma** (`1,42`) | 24,063 | trailing id in `url` (`…-74630.html`) | `Perfume`/`Brand` are lowercase URL slugs — never use them for display. `Perfumer1 = "unknown"` is a placeholder. 24,059 ids exist in `fragrantica`. Unique contribution: **`Country`** (brand country, 54 values, no conflicts per brand). |
| `fra_perfumes` | `fragrantica_fra_perfumes.zip` → `fra_perfumes.csv` | UTF-8, comma | 70,103 (69,948 unique URLs) | trailing id in `url` | `Name` fuses name + brand + gender (`9am Afnanfor women`); `Description` has spaces stripped around links (`9ambyAfnanis…`). `Main Accords`/`Perfumers` are Python-list literals — parse with `ast.literal_eval`, never `eval`. 70,076 ids exist in `fragrantica`; it adds almost nothing new — use it only as a fallback for the ~27 ids missing from `fragrantica`. |
| `parfumo` | `parfumo_data_clean.csv` | UTF-8 bytes but the text is **double-encoded mojibake** (`Tabac Ã‰carlate` → `Tabac Écarlate`); `NA` = missing | 59,325 (59,281 unique URLs) | the `URL` path after `/Perfumes/` (e.g. `Creed/aventus`; only ~500 URLs carry a numeric id); ignore the sparse `Number` column | Names often embed the brand and a year (`Samsara Guerlain 1989 Eau de Parfum`: ~14.8k rows contain the brand, ~9.6k a year). Repair text with `s.encode("cp1252").decode("utf-8")` when it round-trips cleanly, otherwise keep the original (unit-test this). Rating is **0–10**. `Concentration` is 21% filled and includes non-fragrance products (After Shave, Body Spray, Solid Perfume, Perfume Oil) — keep the value as given. `Perfumers` may contain a transliteration after ` / ` — keep the Latin part. At least ~18.6k rows match a Fragrantica record on plain brand + name (measured before stripping brand/year tokens, so expect more); the rest are Parfumo-only. |
| `luckyscent` | `final_perfume_data.zip` → `final_perfume_data.csv` | **not** valid UTF-8 or strict cp1252 — decode cp1252 and fall back to latin-1 for undefined bytes (e.g. `0x9d`) | 2,191 | none — synthesize `sha1(brand|name)` | `Name` embeds the concentration (`Tihota Eau de Parfum`). `Notes` is an unstaged list with a leading space. Unique contribution: editorial `Description` and `Image URL`. ~1.4k rows match a Fragrantica record. |

### Signal density already measured (re-verify and report your own numbers)

Counts are over the 140,228 Fragrantica records unless stated. "≥5 votes" means the aggregate has at least five votes behind it.

| Attribute | Coverage | Proposed |
|---|---|---|
| Official gender label | 100% | include |
| Olfactory family, parsed from the description (`… is a Floral Green fragrance for …`; 53 values) | 117,313 (84%) | include |
| Accords with strength | 98% | include (already modelled) |
| Tiered notes with vote weight / flat notes | 70% / 28% | include; add note weight and an unstaged stage |
| Rating average + count (vote_count > 0) | 121,232 | include |
| Season votes ≥5 | 94,838 | include (existing `fragrance_seasons`) |
| Daypart (day/night) votes ≥5 | 81,436 | include |
| Sillage votes ≥5 | 78,392 | include → existing `projection_level` |
| Longevity votes ≥5 | 75,740 | include → existing `longevity_score` |
| Perceived-gender votes ≥5 | 69,409 | include |
| Price-value votes ≥5 | 65,083 | include |
| have / had / want counts, popularity magnitude | 136,977 | include (default sort order) |
| "Reminds me of" similar perfumes (voted) | 98,621 | include |
| "Also liked" similar perfumes (algorithmic) | 94,584 | include |
| Perfumers (Fragrantica + fra_cleaned; Parfumo adds more) | 53,017+ | include |
| Collection / product line | 42% | include |
| Brand country (fra_cleaned) — fragrances whose brand gets a country | 67,305 | include on `brands` |
| Image URL (rebuildable from Fragrantica id; Luckyscent for its rows) | ~100% of Fragrantica rows | include |
| Concentration (parsed from Fragrantica names / Parfumo column / Luckyscent names) | ~5% / 21% / most | include; column becomes nullable |
| `ai_summary` pros/cons | 12,788 (9%) | **exclude** — below threshold and third-party generated text |
| Rating/longevity/sillage histograms | same as averages | exclude (store average + vote count only) |
| Occasions | 0 in every source | exclude — leave empty |

**Inclusion rule** (apply it to anything you find that is not listed): include an attribute if it holds a meaningful value (not blank, `NA`, `unknown`, or an all-zero vote block) for at least **20% of the final canonical catalog**, or if it directly powers an existing screen (collection, fragrance detail, discover, layering, insights). Put every excluded attribute and its measured coverage in the import report.

## Phase 1 — identity, de-duplication and merge rules

### Normalisation helpers (pure functions, fully unit-tested)

- `fold(text)`: NFKD, strip combining marks, lowercase, `&` → `and`, non-alphanumerics → single space, trim.
- `brand_key = fold(brand)`, plus an explicit alias table `datasets/mappings/brand_aliases.csv` (`alias,canonical`) for houses spelled differently across sources. Seed it with the highest-volume unmatched brands from your first matching run and review it by hand; do not fuzzy-match brands automatically.
- `name_key = fold(name)` with concentration tokens removed (`extrait de parfum`, `extrait`, `eau de parfum`, `eau de toilette`, `eau de cologne`, `parfum`, `cologne`, `edp`, `edt`, `edc`, and similar), with the brand name removed wherever it appears as a whole-word sequence (Parfumo `Samsara Guerlain 1989 …`, `fra_perfumes` `9am Afnanfor women`), and with a standalone 4-digit year removed (use that year as the release-year hint when the source's year field is empty).
- `parse_concentration(name)`: return a canonical label (`Extrait de Parfum`, `Parfum`, `Eau de Parfum`, `Eau de Toilette`, `Eau de Cologne`, …) or `None`. Keep the display name unchanged.

### Canonical identity

A canonical fragrance is identified by its **source records**, not by its name. Every source row becomes a `fragrance_sources` row with a unique `(source, source_record_id)`, attached to exactly one canonical fragrance.

Matching, in order:

1. **Fragrantica id join (exact).** `fra_cleaned` and `fra_perfumes` attach to the `fragrantica` record with the same id. Duplicate rows inside `fra_perfumes` collapse onto one source record.
2. **Fragrantica internal duplicates.** 1,601 brand + name groups contain more than one Fragrantica id; many are real distinct releases (reissues years apart, male vs female versions). Merge two Fragrantica records only when `brand_key`, `name_key`, release year and gender are all equal (two unknown years count as equal, matching the `NULLS NOT DISTINCT` backstop index below) **and** their parsed concentrations are equal or at least one is unknown (about 562 rows by my count). The survivor is the record with the highest `vote_count`; the other ids stay as extra source records pointing at the survivor.
3. **Parfumo and Luckyscent → canonical.** Block on `brand_key`, compare `name_key`. A candidate is compatible when concentration is equal or unknown on either side, and release year is equal or unknown on either side. Exactly one compatible candidate → attach. Several → prefer an exact year match, then an exact concentration match, then the one with the highest popularity **only if** the others are clearly worse; otherwise treat as ambiguous. If there is no exact `name_key` match, you may use `rapidfuzz` `token_sort_ratio ≥ 95` within the same brand (add it as a locked dependency), and only when it produces a single candidate.
4. **Unmatched rows become new canonical fragrances**, but first de-duplicate them among themselves with the same rules (e.g. two Parfumo rows for the same perfume).
5. **Ambiguous rows are never inserted as new fragrances** (that would create a duplicate) and never attached by guesswork. Write them to `unresolved_matches.csv` in the report with their candidates. Target under 1% of Parfumo + Luckyscent rows; if you are above that, improve the rules or aliases before continuing.

Member-owned custom fragrances are never matched, merged or modified.

### Survivorship (which source wins each field)

When a higher-priority source has no value, fall through to the next. Record which source supplied each canonical field so this is auditable.

| Field | Priority |
|---|---|
| display name | fragrantica → parfumo (repaired) → luckyscent → fra_perfumes |
| brand display name | fragrantica → parfumo → luckyscent |
| brand country | fra_cleaned |
| concentration | parsed from fragrantica name → parfumo `Concentration` → parsed from luckyscent name |
| release year (1700–2100 only) | fragrantica → fra_cleaned → parfumo |
| gender | fragrantica → fra_cleaned → fra_perfumes (`for women` / `for men` / `for women and men`) |
| description | luckyscent editorial → fragrantica → nothing (skip `fra_perfumes`; its text is damaged) |
| olfactory family | parsed from the fragrantica description |
| product line | fragrantica `collection` |
| image URL | fragrantica (`https://fimgs.net/mdimg/perfume/375x500.{id}.jpg`) → luckyscent |
| notes | **one** source per fragrance, not a union: fragrantica tiered (with weights) → fragrantica flat → parfumo staged → fra_cleaned staged → luckyscent flat |
| accords | **one** source per fragrance: fragrantica (strength ÷ 100) → fra_cleaned `mainaccord1..5` (weights 1.0, 0.8, 0.6, 0.4, 0.2) → parfumo `Main_Accords` (same positional weights) → fra_perfumes |
| perfumers | union across all sources, de-duplicated by `fold(name)`, dropping `unknown` |
| rating average (0–5) and count | vote-weighted mean of fragrantica (1–5) and parfumo (0–10 ÷ 2). Do not also count `fra_cleaned`/`fra_perfumes` ratings; they are older snapshots of the same Fragrantica votes. Keep each source's raw rating on its `fragrance_sources` row. |
| longevity score (0–10) | fragrantica longevity average (1–5) mapped linearly to 0–10, only with ≥5 votes |
| projection level | fragrantica sillage average (1–4): < 1.5 `intimate`, < 2.5 `moderate`, otherwise `strong`, only with ≥5 votes |
| seasons | fragrantica season votes, only with ≥5 total votes; `autumn` → `fall`; weight = votes ÷ the fragrance's highest season vote |
| daypart, perceived gender, price value, have/had/want, popularity | fragrantica aggregates |
| similar fragrances | fragrantica `reminds_me_of` (with votes) and `also_liked`, resolved to canonical ids (so merged duplicates point at the survivor); drop references to ids not in the catalog and self-references |

Canonicalise note and accord vocabularies: use the Fragrantica note slug as the note identity where present (its display name can differ, e.g. slug `Floral-Notes` / name `Flowers`), otherwise `fold(name)`. Add a small reviewed alias table for obvious cross-source accord variants (e.g. Parfumo `Leathery` → `leather`, `Woody` → `woody`).

## Phase 1 — schema changes (one new migration)

Adjust the list if your own profiling disagrees, but justify every change against the inclusion rule. Update the SQLAlchemy models, the migration (with a working `downgrade`), and the naming-convention-compliant constraint names together.

**`brands`**
- add `country` `String(80)` nullable.

**`fragrances`**
- widen `name` to `String(255)` (the longest source name is 166 characters).
- make `concentration` nullable (most Fragrantica records do not state one). Update the API schema and every frontend consumer to handle `null`.
- add `gender` `String(10)` nullable, check `IN ('male','female','unisex')`.
- add `olfactory_family` `String(60)`, `product_line` `String(160)`, `image_url` `String(512)` (keep `image_blob_path` for member uploads).
- add `rating_average` `Numeric(3,2)` (check 0–5) and `rating_count` `Integer`.
- add `popularity_score` `Integer` (Fragrantica `magnitude`) with a descending index for default ordering.
- add `search_text` `String` — accent-folded `brand + name + concentration`, written by the importer and by custom-fragrance creation — with a `pg_trgm` GIN index.
- replace `uq_fragrances_shared_identity` with a backstop unique index on shared rows over `(brand_id, lower(name), concentration, release_year, gender)` using `NULLS NOT DISTINCT` (PostgreSQL 15+). The importer's merge rules are the real de-duplication; this index only guarantees nothing slips through.

**`fragrance_notes`**
- add `weight` `Numeric(3,2)` nullable (Fragrantica note weight ÷ 100).
- extend the `stage` check to allow `'general'` for unstaged ("flat") notes.

**New tables**
- `perfumers` (`id`, `name`, `slug` unique) and `fragrance_perfumers` (`fragrance_id`, `perfumer_id`; composite PK; cascade on fragrance delete).
- `fragrance_community_stats` (1:1 with `fragrances`, PK `fragrance_id`): `longevity_average`, `longevity_votes`, `sillage_average`, `sillage_votes`, `price_value_average`, `price_value_votes`, `have_count`, `had_count`, `want_count`, `perceived_female`, `perceived_female_leaning`, `perceived_unisex`, `perceived_male_leaning`, `perceived_male`, `day_votes`, `night_votes`, `voters`, `captured_at` (from `meta.scraped_at`).
- `fragrance_similarities` (`fragrance_id`, `similar_fragrance_id`, `kind` check `IN ('reminds_me_of','also_liked')`, `rank`, `up_votes`, `down_votes` nullable; PK `(fragrance_id, similar_fragrance_id, kind)`; check the two ids differ; index on `similar_fragrance_id`).
- `fragrance_sources` (`id`, `fragrance_id` FK cascade, `source` check in the five source ids, `source_record_id`, `source_url`, `raw_name`, `raw_brand`, `rating_raw`, `rating_scale`, `rating_count`, `field_origins` JSON — which canonical fields this source supplied, `import_run_id`; unique `(source, source_record_id)`).
- `catalog_import_runs` (`id`, `started_at`, `finished_at`, `status`, `inputs` JSON with each archive's sha256 and row count, `counts` JSON).

**Extensions / infra**
- The migration runs `CREATE EXTENSION IF NOT EXISTS pg_trgm`. Azure Database for PostgreSQL Flexible Server only allows allow-listed extensions: add a `azure.extensions` server parameter containing `PG_TRGM` in `infra/modules/postgres-settings.bicep`, update `infra/tests/Test-CompiledInfrastructure.ps1` if it pins resource counts, and check that the migration job's database role is allowed to create the extension. Local compose (PostgreSQL 18) already ships `pg_trgm`.

Expected size is roughly 180k fragrances, ~1.5M note links, ~2.5M similarity rows — comfortably inside the dev server's 32 GB, but do not store raw JSON payloads per source.

## Phase 2 — the importer

Create `apps/api/src/scentiq_api/catalog_import/` as a package: one reader per source (each yielding typed, already-normalised dataclasses), `normalize.py`, `match.py`, `merge.py`, `load.py`, `report.py`, and `__main__.py`.

```powershell
uv run --directory apps/api python -m scentiq_api.catalog_import `
  --raw-dir ../../datasets/raw `
  --report-dir ../../datasets/reports `
  [--dry-run] [--only fragrantica,parfumo] [--purge-demo-catalog]
```

Requirements:

- **Two stages.** Build the whole canonical set in memory first (stream the 530 MB JSONL; keep only the fields you need), then load. `--dry-run` runs everything except the database writes and still produces the report.
- **Fast bulk load.** Use psycopg `COPY` into temporary staging tables, then set-based `INSERT … ON CONFLICT … DO UPDATE … WHERE … IS DISTINCT FROM …` into the real tables so unchanged rows are not rewritten and `updated_at` only moves on real changes. No per-row ORM inserts. Target: under 10 minutes locally.
- **Stable ids.** Canonical fragrance UUIDs are `uuid5` of the primary source key (e.g. `fragrantica:9828`). On re-runs, look up existing canonical ids through `fragrance_sources` first, so ids stay stable even if merge rules change. Member collections reference these ids, so they must never churn.
- **Idempotent.** A second run over the same inputs must report zero inserts, zero updates, zero deletes. Test this.
- **Replace children per fragrance.** For each shared fragrance in the canonical set, its notes, accords, seasons, perfumers, stats and similarities are replaced to match the canonical set exactly. Shared fragrances that disappear from the inputs are left in place and listed in the report — never deleted automatically.
- **One transaction for the load stage**, recorded in `catalog_import_runs`, so a failure leaves the previous catalog intact.
- **Demo catalog cleanup.** `--purge-demo-catalog` removes the fictional shared brands/fragrances created by `seed.py` (brand slugs `scentiq-atelier`, `scentiq-botanica`, `scentiq-studio`) **only if** no member data references them; referenced ones are listed in the report and kept.
- **Report** (`--report-dir`, add `datasets/reports/` to `.gitignore`): `summary.json` and `summary.md` with rows read / rejected (with reasons) per source, matches per rule, Fragrantica duplicates merged, new fragrances per source, final catalog counts, attribute coverage of the final catalog (the table above, recomputed), excluded attributes, and `unresolved_matches.csv`.
- Keep this runnable without Azure credentials. It only needs `DATABASE_URL`, the same as `scentiq_api.seed`.

### Tests

- Unit tests for every normaliser and parser: mojibake repair, cp1252/latin-1 fallback, decimal comma, `ast.literal_eval` lists, concentration parsing, `name_key`, year clamping, sillage → projection and longevity mappings, season weights, positional accord weights.
- Unit tests for the matcher with small fixture files (a few rows per source in `apps/api/tests/fixtures/catalog_import/`) covering: id join, internal Fragrantica duplicate merge, distinct reissues kept apart (e.g. Samsara 1989 vs 2021), Parfumo match with and without concentration, an ambiguous case landing in the report, and a Parfumo-only record inserted once.
- Integration tests (marked `integration`) that load the fixtures into the compose database, assert the backstop index holds, run the import twice and assert the second run changes nothing, and assert member-owned rows are untouched.
- Do not make any test depend on the real 140 MB dataset.

### Verification SQL (run after the real import; paste results into the PR)

```sql
-- Must return zero rows: no duplicate shared fragrances
SELECT brand_id, lower(name), concentration, release_year, gender, count(*)
FROM fragrances WHERE owner_user_id IS NULL
GROUP BY 1, 2, 3, 4, 5 HAVING count(*) > 1;

-- Every source record maps to exactly one fragrance (enforced by the unique key, but show the totals)
SELECT source, count(*) FROM fragrance_sources GROUP BY source ORDER BY source;

-- Records enriched by more than one dataset
SELECT count(*) FROM (
  SELECT fragrance_id FROM fragrance_sources GROUP BY fragrance_id HAVING count(DISTINCT source) > 1
) merged;
```

Spot-check and include in the PR: Fragrantica id 1 (Azzaro *Orange Tonic*: gender female, product line TONIC, top note Orange weight 1.00, summer the strongest season, perfumer Nathalie Feisthauer), Fragrantica id 9828 (Creed *Aventus*, which should also carry a Parfumo source), one Parfumo-only record, and one Luckyscent record showing its editorial description and image.

Expect roughly 175k–185k shared fragrances (≈140k Fragrantica minus merged duplicates, plus up to ≈40k Parfumo-only and ≈0.8k Luckyscent-only). Explain any large deviation.

### Running it

1. Locally: `docker compose … up -d db`, `alembic upgrade head`, `python -m scentiq_api.catalog_import --dry-run`, review the report, then run for real, then run again to prove idempotency.
2. Azure dev: write `docs/runbooks/catalog-import.md` covering `git lfs pull`, obtaining `DATABASE_URL` for `scentiq-rg-dev-eus` the way the existing runbooks do, adding and then **removing** a temporary firewall rule for the operator's IP, running the migration via the normal deploy (not by hand), then running the importer with `--purge-demo-catalog`, and the verification SQL. If you do not have Azure credentials, stop after the local run and leave the runbook for the operator — do not create or reconfigure Azure resources beyond the `azure.extensions` parameter above.
3. Make `seed.py` stop inserting fictional brands and fragrances. For local development it should give the demo user a collection built from real imported fragrances (pick ~12 popular ones across different olfactory families by Fragrantica id) and exit with a clear message if the catalog has not been imported. Leave the self-contained test fixtures in `apps/api/tests/domain_fixtures.py` fictional.

## Phase 3 — API and frontend on real data

### API

- `FragranceSummary`: add `gender`, `olfactory_family`, `image_url`, `rating_average`, `rating_count`, `top_accords` (up to 3 names); `concentration` becomes nullable.
- `FragranceDetail`: add `product_line`, `brand.country`, `perfumers`, note `weight`, `community` (the stats block, `null` when there are no votes), `similar` (up to 8 `reminds_me_of` fragrances as summaries, ordered by net votes), and `sources` (source name + URL, for attribution).
- `GET /api/v1/fragrances`: add `offset`, filters `gender`, `family`, `season`, `accord`, and `sort=relevance|popular|rating|name`. With `q`, rank by trigram similarity on `search_text` then popularity; without `q`, default to popularity. Keep the member-visibility rule (shared + the caller's own custom rows).
- `GET /api/v1/discover`: shared fragrances the member does not own, scored deterministically against their owned collection — taste match (weighted accord and note overlap), collection expansion (accords/families the collection lacks), redundancy risk (highest similarity to an owned fragrance, using `fragrance_similarities` and accord overlap). Supports the same filters. Document the formula in the service docstring.
- `GET /api/v1/layering/suggestions`: pairs drawn from the member's owned collection, scored from shared notes, complementary accords and season overlap, with a `mode` of Safe / Contrast / Experimental. Deterministic and documented.
- Custom-fragrance creation must populate `search_text` too.
- Regenerate contracts with `pnpm contracts` and keep `pnpm contracts:check` green.

### Frontend

Every screen that currently imports `@/lib/demo` (`app/page.tsx`, `features/discover`, `features/layering`, `features/week`, `features/agent`) must stop using the fictional catalog.

- **Discover**: server-rendered from `/api/v1/discover`. Replace the illustrative-price budget filter (no source has prices) with filters the data supports: family, season, gender, and a value-for-money minimum from `price_value_average`. Show real image, family, rating, top accords, and the three scores. "Add to wishlist" calls the existing `addToCollection` action with `status: "wishlist"`. Remove the "Curated demo" and "On the horizon" placeholder cards and the preview notice.
- **Layering Lab**: pickers list the member's owned fragrances; guidance comes from `/api/v1/layering/suggestions`. With fewer than two owned fragrances, show an empty state linking to the collection. Keep the "guidance, not chemistry" note; drop the "sample data" wording.
- **Fragrance detail and collection**: show the new attributes — image (with a fallback to the existing deterministic tone art from `lib/tone.ts` when there is no image or it fails to load), gender, family, product line, brand country, perfumers, rating with count, community longevity/sillage/price-value, season and day/night bars, notes by stage with weights (`general` stage labelled "Notes"), similar fragrances linking to their detail pages, and a source attribution line. Missing values render as "Not enough community data", never as zero.
- **Add-fragrance search**: use the improved search (debounced, relevance-ordered, paginated) so a 180k-row catalog is usable.
- **Week planner and Agent**: there is still no weather or calendar provider. Keep those inputs labelled as previews, but move the sample weather/events into an explicitly named `lib/preview/` module, and make every fragrance they mention come from the member's real collection, chosen deterministically from real season, daypart, longevity and projection data. The Agent's quick answers must be computed from the member's real collection and insights; if the collection is empty, say so and link to it.
- **Landing page (`app/page.tsx`)**: it is public and must not call authenticated endpoints or loosen auth. Replace the demo lookup with a static, clearly labelled example card that names no fictional house.
- **Images**: render remote images with `next/image` and `remotePatterns` for `fimgs.net` and `static.luckyscent.com` (or a plain lazy `<img>` with `onError` fallback). Add a `NEXT_PUBLIC_CATALOG_REMOTE_IMAGES` flag, on by default, so hotlinked third-party images can be switched off without a deploy of new code.
- **Attribution**: a footer/credits line in the app shell: "Catalogue data includes Fragrantica data via Kaggle (ledecanteur/fragrantica-perfumes), CC BY-NC-SA 4.0, and Parfumo and Luckyscent listings."
- Delete `apps/web/lib/demo/index.ts`, `apps/web/lib/demo/demo.test.ts` and any `apps/web/types/demo.ts` types that no longer have a consumer; update or replace the affected Vitest and Playwright tests so they assert real-data behaviour against mocked API responses.
- Update `README.md` and `docs/architecture/authenticated-personal-application.md`, which currently say external datasets are future work.

## Definition of done

- [ ] One migration adds the schema above; `alembic upgrade head` and `downgrade` both work on a copy of the local database.
- [ ] The importer runs end to end locally over all five source files; the second run reports zero changes.
- [ ] The duplicate-check SQL returns zero rows; unresolved ambiguous matches are under 1% of Parfumo + Luckyscent rows and listed in the report.
- [ ] Member-owned fragrances and member data are unchanged (row counts and checksums before/after in the PR).
- [ ] The final attribute-coverage table and the list of excluded attributes are in the PR description.
- [ ] `rg "lib/demo" apps/web` returns nothing, and none of the fictional brand names (Atelier North, Ninth House, Maison Sillage, Common Air, Parable, Tide Archive, Orison, Blue Hours, Serein, Daymark, ScentIQ Atelier, ScentIQ Botanica, ScentIQ Studio) render anywhere.
- [ ] All CI gates listed under Ground rules pass, including the privacy check.
- [ ] `docs/runbooks/catalog-import.md` exists; the Azure dev import has been run, or the PR clearly says it is waiting for an operator.
- [ ] The PR description lists open questions, at minimum: the licence of the Parfumo, Luckyscent and fra_* scrapes; whether hotlinked images are acceptable; and any brand aliases you were unsure of.
