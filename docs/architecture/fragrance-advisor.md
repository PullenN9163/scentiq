# Fragrance advisor

The Agent uses the same deterministic wear, layering, discovery, collection, and insights services as the rest of ScentIQ. The model interprets questions and explains service results. Recommendation rankings, roles, application order, and spray splits remain domain-service outputs.

## Service boundary

The browser posts to the same-origin Next.js `/api/agent/chat` route. The server-only API client attaches the Clerk session token and forwards to `POST /api/v1/agent/chat`. FastAPI verifies the session and binds the internal member identifier to a read-only tool dispatcher. No tool accepts a member identifier. Private custom fragrances remain subject to the existing visibility predicates.

The API uses Azure OpenAI's stable v1 Responses endpoint with HTTP streaming and function tools. An application policy, versioned `scentiq-agent-v1`, requires fresh tool evidence on every question. The first provider turn requires a tool; text emitted before any successful tool result is discarded. Result cards are constructed exclusively from validated, minimized service results. A model explanation supplements those cards.

No chat table or persistent provider conversation is created. The UI holds its active session in memory and sends at most eight recent user/assistant turns, each bounded to 2,000 characters. The current message is bounded to 2,000 characters, combined text to 12,000 characters, and the actual HTTP body to 65,536 bytes at both service boundaries. Provider requests set `store: false` and include a SHA-256 hash of the internal identifier as the safety identifier.

## Tools and bounds

Available tools are `get_today_recommendations`, `get_week_plan`, `get_collection`, `get_collection_insights`, `get_recent_wears`, `get_neglected_fragrances`, `get_discover_recommendations`, `get_layering_suggestions`, `evaluate_layering_stack`, `get_fragrance_detail`, and `preview_recommendation`.

Pydantic validates arguments and rejects additional fields. Queries, result counts, dates, enum values, and stack sizes are bounded. User-selected layering stacks require owned fragrances; catalog detail may also return a visible shared fragrance. There are no network-fetch, SQL, shell, code-execution, calendar-write, or other arbitrary tools. Context refresh and domain calculations run locally using a separate worker-owned database session for each serialized tool invocation.

The request allows six total tool attempts and four model turns, with a 25-second overall response deadline. Operators may lower these limits but cannot raise their validated ceilings. Ten percent of the time budget is reserved for deterministic fallback. A timed-out worker may finish its finite service operation and close its own session, while the response stops waiting; it never reuses the request's session. Recommendation tools can persist the same recommendation cache used by Today and My Week, but the model cannot accept, reject, wear, or mutate a collection item.

Wear-tool payloads use a card-sized shortlist before the global 24,000-character output limit. Week summaries prioritize seven daily contexts and show one alternative per recommendation; Today shows up to three contexts and two alternatives. The shortlist retains a saved selected alternative and the full card scoring, context, image, and decision fields. Omitted event contexts and alternative options are disclosed in the plan's gaps, with the complete plan available in Today or My Week.

## Privacy and telemetry

Tool output excludes member/email identifiers, private notes, calendar titles, descriptions, attendee lists, meeting URLs, raw source payloads, and tokens. Catalog note lists are retained as source evidence; private free-text note fields are removed. Results are bounded before they are forwarded to the model. A member's own typed question is sent to the configured provider, so the UI should not encourage entering credentials or private calendar content.

Agent diagnostics record duration, deployment, policy version, tool count and names, provider failure category, timeout/cancellation, fallback state, and token counts when returned. Raw prompts, conversation turns, tool payloads, provider errors, and secrets are not logged. Token counts are usage metadata; ScentIQ does not calculate a price without an operator-supplied pricing source.

## Streaming protocol

The response is UTF-8 `application/x-ndjson` with `Cache-Control: no-store`. Each line is an independent JSON event:

```json
{"type":"status","label":"Checking your ScentIQ context…"}
{"type":"tool_started","tool":"get_collection_insights","label":"Comparing your collection…"}
{"type":"tool_finished","tool":"get_collection_insights","label":"Context ready"}
{"type":"card","card":{"kind":"insights","data":{"total_wears":3}}}
{"type":"text_delta","delta":"Your recorded history…"}
{"type":"done"}
```

Cards have the kinds `recommendation`, `week`, `collection`, `insights`, `wears`, `discover`, `layering`, or `fragrance`. Their data uses the corresponding authoritative service response, after privacy filtering. `fallback` carries a safe display label. Provider debug events are never forwarded. The browser parser handles fragmented UTF-8 and incomplete lines, rejects unsupported events, bounds response size, and treats a stream without `done` as interrupted.

The composer supports Enter, Shift+Enter, and cancellation. Screen-reader announcements report preparation, completion, or failure rather than reading every token. Cards link to the relevant ScentIQ surfaces; wear cards reuse the normal confirmation flow and layering cards preload the selected owned stack in Layering Lab.

## Failure behavior

With inference disabled, missing deployment configuration, provider errors, invalid tools, exhausted budgets, or timeout, common requests use deterministic intent matching against the same services. The response marks that the AI explanation is unavailable. Unsupported requests receive a concise list of supported capabilities; unavailable member context produces a safe retry message. Provider errors and account details are not exposed to the browser.

See the [advisor operations runbook](../runbooks/fragrance-advisor.md) for configuration and deployment prerequisites.
