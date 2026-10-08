# Wear intelligence

Today, My Week and the advisor use `WearRecommendationService`. The existing hybrid discovery/layering snapshot contract remains available. Browser requests terminate at the authenticated Next.js server; private scoring and persistence run in FastAPI.

## Score version wear-v1

Each owned fragrance receives these components, followed by penalties and a clamp to 0–100:

| Component | Maximum | Rule |
| --- | ---: | --- |
| Occasion | 25 | Recorded occasion weight × 25; otherwise same-occasion personal wear ratings give 12.5 + 2.5 × (mean rating − 3); otherwise 12.5. An unrated matching wear contributes the neutral personal rating of 3. |
| Weather | 20 | Neutral 10 without temperature/projection; otherwise 15, falling to 6 for ≥28°C with strong projection or longevity ≥8, or 7 for ≤5°C outdoors with intimate projection. |
| Season | 15 | Recorded current-season weight × 15; neutral 7.5 without season metadata. Southern-hemisphere locations reverse seasons. |
| Setting/projection | 10 | Neutral 5 without setting evidence; 9 for compatible known projection, 3 for strong projection in an indoor/work/formal setting. |
| Time of day | 10 | Proportion of source community votes for day or night × 10; neutral 5 without votes. Night runs from 18:00 through 05:59 in the member timezone. |
| Preference | 10 | Start at 5; add personal item rating −3, mean feedback rating −3 capped ±2, projection match +1/mismatch −1, and longevity fit max(−1, 1 − absolute difference/3). Clamp to 0–10. |
| Rotation | 10 | 10 if never worn or last worn ≥7 days; 8 after ≥3 days; 5 after ≥1 day; otherwise 2. |

Penalties: last wear under one day −8 or under three days −4; 30-day wear frequency −min(6,count); same-occasion rejections −min(8,2×count); conservative context with strong projection −4; extreme-heat conflict −4. Total penalties are capped at −30. Missing metadata incurs no penalty. Humidity and precipitation are displayed when known but carry no scoring adjustment in this version.

Feedback history is bounded to the preceding year and wear frequency/rejections to 30 days. History is evaluated through the later of the context time and current time, so a wear logged today immediately affects Today. Recency is measured in completed 24-hour intervals. Ties sort by fragrance name, fragrance ID and collection-item ID; bottle/decant duplicates produce one fragrance candidate.

Reasons are the strongest supported positive components, sorted deterministically. Evidence coverage is the number of supported components divided by seven. Rotation always has collection-history evidence; missing catalog data lowers coverage. Labels use ≥0.75 High, ≥0.4 Moderate, otherwise Limited evidence. Coverage is not a probability.

Spray guidance starts at intimate 5, moderate 4, strong 3, unknown 4. Subtract one for ≥28°C and one for indoor/work/formal context. Add one for intimate projection outdoors at ≤5°C. Clamp to 1–8 and the member's maximum. This is starting guidance rather than a performance guarantee.

Positive match explanations require supported inputs and more than half of the component�s normalized fit. Poor matches cannot produce positive season, occasion, projection or weather claims. Performance preferences count toward evidence only when the corresponding fragrance performance is known.

## Persistence and ownership

`recommendations` stores a context, fingerprint, selected score and evidence. `recommendation_candidates` stores up to six ranked candidates and their individual guidance. Fingerprints canonicalize ranking inputs, preferences, contextual weather/history and algorithm version. A unique member/context/fingerprint/version constraint and transaction savepoint make repeated generation idempotent; changed inputs create historical records rather than overwrite them.

Visible events from selected calendars generate separate contexts when occasion, formality, setting or daypart differ. Hidden events never generate a context. Open-day contexts use a stable 09:00 local time. Missing timezone uses UTC with a disclosed gap; missing weather uses neutral scoring. Provider refresh failures preserve cached input.

`recommendation_decisions` persists accepted/rejected/replaced/dismissed. Replacements must be currently owned. Converting a recommendation to a wear writes its decision and `wear_logs.recommendation_id` in one transaction. Private `wear_feedback` can be read or replaced only through the caller-owned wear log. Account deletion cascades through recommendation decisions, candidates, wear history and feedback.

## API

- `GET /api/v1/recommendations/today` and `/week`: persisted plans and alternatives.
- `POST /api/v1/recommendations/preview`: explicit contextual what-if, including user-supplied weather overrides.
- `POST /api/v1/recommendations/{id}/decision` and `/wear`: ownership-checked choices and logging.
- `GET` and `PUT /api/v1/wear-logs/{id}/feedback`: rating, longevity, projection and private comments.

Apply database migrations before the API revision, then deploy the web revision. Keep the Azure model disabled until its endpoint, deployment and managed identity access are configured. Recommendations operate independently of model availability.
