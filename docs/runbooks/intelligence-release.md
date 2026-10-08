# Fragrance intelligence release

## Release contents

Today and My Week use persisted deterministic recommendations with alternatives, evidence, contextual spray guidance and wear feedback. Layering Lab supports owned pairs and triples, goals, saved stacks and wear/rating history. Insights reports recorded rotation, ratings, cost per wear and collection coverage; Discover offers balance, taste, exploration and seasonal modes with saved wishlist state. Custom fragrance images use authenticated private storage. The advisor streams Azure v1 Responses through server-owned tools and falls back to deterministic results when inference is unavailable.

See the [wear formula](../architecture/wear-intelligence.md), [layering formula](../architecture/layering-intelligence.md), [advisor architecture](../architecture/fragrance-advisor.md), [advisor operations](fragrance-advisor.md) and [image operations](custom-fragrance-images.md).

## Deployment order

1. Apply migrations through `20261007_0008_layer_stacks` before deploying the API revision. Migration `0007` adds persisted contextual recommendations and decisions; `0008` adds normalized stacks and converts legacy pairs.
2. Deploy the API and web revisions together. Preserve Clerk, calendar encryption and provider configuration.
3. Configure private Blob storage for uploaded images; local image storage is intended for development.
4. Configure the Azure inference endpoint, model deployment and managed identity role before enabling live inference. The deterministic advisor remains usable without inference credentials. Do not expose model credentials to the browser.
5. Run the invited-member browser journey against a seeded test environment with Clerk test credentials. Verify Today, Week, advisor, pair/triple save/wear/rating, feedback, images, keyboard use and the configured viewport sizes.

## Validation snapshot - 2026-10-08

| Check | Result |
| --- | --- |
| API unit tests | 389 passed |
| PostgreSQL integration tests | 53 passed |
| Web component and stream tests | 131 passed |
| Python lint/format and ESLint | Passed |
| Strict mypy and TypeScript | Passed |
| Generated API contract drift | Passed |
| Production web build and API/web Docker builds | Passed |
| PostgreSQL downgrade to base, upgrade to head, schema drift | Passed |
| Bicep compilation, development parameter compilation, infrastructure safety | Passed |

The signed-in browser journey requires `CLERK_SECRET_KEY`, `E2E_CLERK_EMAIL` and `E2E_CLERK_CODE`; it has not been executed for this release in the local verification environment. Live Azure inference, deployed managed identity access, cloud image storage and visual/accessibility inspection require the configured test deployment. Provider tests use controlled streams and verify tool grounding, ownership, cancellation, timeout and output bounds; they do not validate every factual statement a live model could produce.
