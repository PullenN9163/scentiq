# Layering intelligence

Layering Lab and the fragrance advisor use `LayeringService` to recommend and evaluate combinations of two or three owned fragrances. The production stack algorithm is `layering-v2`, implemented in `services/layer_stack_scoring.py`. Ranking is deterministic; the language model does not score combinations.

Catalog notes, accords, season suitability and performance records support olfactory comparisons. Roles, application order and spray allocations are rule-based starting guidance. Scores do not represent chemical compatibility, skin safety, exact combined longevity or guaranteed performance.

## Stack score

Each fragrance has a weighted profile keyed by recorded accord and note slugs. Accord weights come from the catalog. Notes use their recorded positive weight, with `0.5` for absent or zero note weights. A recorded family contributes `0.5` if its lowercase, hyphenated key is not already present. Repeated keys retain the largest weight.

For two profiles `A` and `B`, weighted overlap is:

```text
overlap(A, B) = sum(min(A[k], B[k])) / sum(max(A[k], B[k]))
```

The sums cover the union of keys; an empty denominator yields zero. Stack components are normalized to `0..1`:

| Component | Production calculation |
| --- | --- |
| Bridge | Pair: weighted overlap. Triple: choose the supporting scent that maximizes the smaller of its anchor overlap and its overlap with the other supporting scent; ties keep the earlier supporting scent. The smaller edge is the bridge component. |
| Novelty | Mean, across supporting scents, of the weighted profile fraction whose keys are absent from the anchor. Empty profiles contribute zero. |
| Complement | `novelty * min(1, 2 * bridge + 0.25)`. Useful contrast receives more credit when a recorded bridge connects it. |
| Season/context | Maximum, across seasons recorded for every selected fragrance, of their minimum season weight. With no common recorded season, the neutral fallback is `0.5`; missing season evidence is reported separately. |
| Projection balance | `max(0, 1 - abs(mean(known_projection) - target))`, or `0.5` without known projection. Targets are `0.75` for more projection, `0.3` for softer/intimate, and `0.5` otherwise. |
| Longevity balance | `1 - (maximum - minimum)` over known longevity scores divided by ten. Fewer than two known scores yield `0.5`. |
| User affinity | Mean fragrance affinity plus bounded feedback from ratings of the same set of fragrance IDs, clamped to `0..1`. |
| Redundancy penalty | Maximum weighted overlap between any two selected profiles. |
| Overload penalty | `min(1, max(0, strong_count - 1) * 0.5)`. For softer/intimate goals, take the larger of this value and `strong_count / stack_size`. |

Projection values are intimate `0.25`, moderate `0.55`, strong `0.9`. A member's custom projection takes precedence, followed by the catalog projection label, then community sillage average divided by four. Values at least `0.8` count as strong. Custom longevity takes precedence over catalog longevity. Unknown performance stays unknown and reduces evidence coverage.

The weighted baseline uses the following coefficients:

| Mode | Bridge | Complement | Season/context | Projection | Longevity | Novelty | Affinity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Balanced | .22 | .20 | .13 | .12 | .08 | .10 | .15 |
| Safe | .32 | .10 | .17 | .16 | .08 | .02 | .15 |
| Contrast | .18 | .27 | .10 | .12 | .08 | .15 | .10 |
| Experimental | .17 | .25 | .08 | .12 | .08 | .20 | .10 |

```text
base = weighted_sum(components)
goal_base = 0.70 * base + 0.30 * goal_fit    # when a goal is selected
score = clamp(goal_base_or_base - 0.18 * redundancy - 0.22 * overload, 0, 1)
```

Scoring uses full precision, then exposes scores and components rounded to four decimal places. A triple is evaluated as a connected stack; its result is not an average of pair compatibility scores.

## Goals and personalization

Profile goals measure the mean weighted share of matching keys in supporting scents. The exact target keys are:

| Goal | Target keys |
| --- | --- |
| Fresher | citrus, fresh, green, aromatic, aquatic, fresh-spicy |
| Warmer | amber, vanilla, spicy, warm-spicy, woody, resin, tobacco, gourmand |
| Sweeter | sweet, vanilla, gourmand, fruity, honey, caramel |
| Darker | oud, leather, smoky, tobacco, incense, patchouli, woody |
| Cleaner | fresh, musky, soapy, citrus, aldehydic, aquatic |
| Daytime | citrus, fresh, green, aquatic, aromatic |
| Evening | amber, woody, vanilla, leather, tobacco, warm-spicy |

For daytime/evening, available supporting-fragrance community day/night vote fractions are averaged with the profile goal score. A season goal uses the mean recorded suitability for that season over every selected fragrance, with zero for absent records. Softer, intimate and projection goals use the projection-balance component as goal fit. The Lab exposes profile goals only when matching keys exist in the owned collection, performance goals when projection is recorded, and season goals when season records exist.

Fragrance affinity is `0.5 + 0.1 * (rating_or_3 - 3) + 0.01 * min(wear_count, 10)`. For the same fragrance set, historical layering affinity is `0.5 + (mean_stack_rating - 3) / 4`, or `0.5` without ratings. The scorer adds half of its difference from `0.5` to mean fragrance affinity. A five-star versus one-star layering history can change the balanced score by at most `0.075`; selected goals reduce this influence further through the `0.70` baseline factor. Sparse history cannot replace catalog scoring.

## Candidate bounds and evidence

Owned fragrances are read in name/ID order. Automatic support scoring considers the first 200 items. An explicit anchor must belong to the authenticated member's owned collection. Surprise mode uses at most eight anchors. Each anchor is paired with the support pool; the best eight pair bases each generate third scents from at most sixteen ranked supports. Identical fragrance sets are deduplicated. Automatically generated triples with overload penalty `1` are excluded. Explicit custom stacks remain inspectable and include warnings.

The optional `stack_size=2|3` filter applies before result truncation, so requests for triples return triples even when pairs have equal or higher scores. API limits range from one to fifty results. No automatic four-fragrance stacks are generated.

Evidence coverage is the mean presence of five categories across the stack: notes, accords, seasons, known projection and known longevity. Labels are strong at least `0.85`, partial at least `0.65`, and limited below `0.65`. Limited evidence adds a warning and reduces the starting spray ceiling. Warnings also identify redundancy above `0.7`, overload above zero, and bridge strength below `0.15`.

## Application guidance

The first selected fragrance is the anchor. A triple assigns bridge to the supporting fragrance chosen by the bridge calculation, and accent to the remaining fragrance. A pair assigns accent to its supporting fragrance.

Starting application order sorts descending projection, then descending longevity, then original selection order. Ordering uses neutral values `0.5` projection and `5` longevity for missing data; it does not fabricate recorded performance.

The starting total spray ceiling is three for softer/intimate goals or two or more strongly projecting scents; four for one strongly projecting scent; otherwise six. Limited evidence caps it at four. The member's maximum-spray preference can reduce the ceiling. Each selected fragrance receives one spray, then extra sprays alternate between anchor and bridge/support. The final per-fragrance allocation sums to the total.

A ceiling below the stack size cannot support one spray per selected fragrance. Automatic suggestions omit unsupported sizes, and explicit evaluation or wear logging returns `spray_budget_too_low`. Existing saved history stays visible with an explicit ceiling warning.

## Persistence and API

Migration `20261007_0008_layer_stacks` adds `layer_stacks`, `layer_stack_items` and `layer_stack_wears`, with user deletion cascades. Saved stacks retain name, mode, goal, optional notes, normalized fragrance positions/roles/sprays, original score, component snapshot, evidence coverage and algorithm version. Current suggestions are reevaluated against current metadata and feedback. Stack feedback is scoped to the member and the exact set of selected fragrances.

Legacy `layering_logs` are copied into two-item saved stacks with their original wear timestamp, rating and note. Unknown historical scores remain zero snapshots tagged `legacy-pair-v1`, with empty components and zero evidence, rather than being presented as reconstructed original scores. Legacy rows remain available to existing consumers and survive downgrade/re-upgrade.

All endpoints are beneath `/api/v1/layering` and derive the member identifier from authentication:

- `GET /intelligence`: supported goals, ranked suggestions and saved combinations.
- `GET /stacks/suggestions`: anchor, mode, goal, optional size and bounded limit.
- `POST /stacks/evaluate`: evaluate two or three distinct owned fragrance IDs.
- `GET /stacks`, `POST /stacks`, `PATCH /stacks/{id}`, `DELETE /stacks/{id}`: list, save, rename and delete.
- `GET /stacks/{id}/wears`, `POST /stacks/{id}/wears`: history and wear logging.
- `PATCH /stacks/{id}/wears/{wear_id}/rating`: update a personal wear rating.

Logging a stack also creates one ordinary wear entry per selected fragrance, using its allocated sprays. Insights and rotation therefore include the scents actually worn. Deleting a saved combination removes its layering history while ordinary fragrance wear logs remain. The legacy `/suggestions` endpoint retains its pair contract for the hybrid bundle during migration.

The browser calls Next.js server actions; only the server attaches the Clerk token and reaches FastAPI. Fragrance ownership, stack ownership and wear ownership are checked on the backend. Cross-member identifiers return the same not-found response as missing identifiers. Private wear notes are retained as member data and are not included in algorithm telemetry.
