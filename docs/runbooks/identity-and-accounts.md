# Runbook: Identity and Accounts

Operational procedures for ScentIQ authentication, member provisioning and account deletion.

## Prerequisites

- A Clerk application for the target environment.
- Key Vault-backed Container App secrets configured (see below).
- Database migrated to `20260923_0003` or later.

## One-time Clerk setup

1. **Restrict enrolment.** The private beta is invite-only. In Clerk, disable public sign-up and add members by invitation or allowlist.
2. **Enable sign-in methods.** Google and passwordless email codes.
3. **Add the JWT template claim.** This step is mandatory.

   ScentIQ creates a member record on their first authenticated request, and the verified token is the only trustworthy source for their email address. Add `email` to the session token template.

   Without this claim every request fails with `401`. That is deliberate: the alternative would be inventing an email or trusting the client.

4. **Register the deletion webhook.** Point a `user.deleted` webhook at `https://<web-host>/api/webhooks/clerk` and record the signing secret.
5. **Note the issuer.** Copy the Clerk Frontend API URL; this is `CLERK_ISSUER`.

## Required secrets

Set all of these as Container App secrets sourced from Key Vault. Never commit a real value.

| Secret | Target | Notes |
| --- | --- | --- |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Web | Public by design; reaches the browser. |
| `CLERK_SECRET_KEY` | Web | Server only. Used to delete an identity. |
| `CLERK_WEBHOOK_SECRET` | Web | Verifies the Svix signature. |
| `CLERK_ISSUER` | API | Authentication fails closed until this is set. |
| `CLERK_AUDIENCE` | API | Omit only if the JWT template sets no audience. |
| `CLERK_AUTHORIZED_PARTIES` | API | Comma-separated origins. When set, a token with no `azp` is refused. |
| `INTERNAL_SERVICE_TOKEN` | Web **and** API | Must be identical in both. Generate at least 32 random bytes. |

`CLERK_JWKS_URL` is optional and defaults to `<CLERK_ISSUER>/.well-known/jwks.json`.

## Azure configuration

Three values are Key Vault secrets. The rest are public identifiers and are passed as plain configuration, because marking a non-secret as secret only makes it harder to diagnose.

### Key Vault secrets

Create these in the development Key Vault and record each secret's URI:

```bash
vault=<key-vault-name>
az keyvault secret set --vault-name "$vault" --name clerk-secret-key --value "<sk_test_…>"
az keyvault secret set --vault-name "$vault" --name clerk-webhook-secret --value "<whsec_…>"
az keyvault secret set --vault-name "$vault" --name internal-service-token --value "$(openssl rand -hex 32)"
az keyvault secret show --vault-name "$vault" --name clerk-secret-key --query id --output tsv
```

The container apps read these through the workload identity, so the values never enter the workflow logs or the repository.

### GitHub repository configuration

| Name | Kind | Value |
| --- | --- | --- |
| `CLERK_SECRET_KEY_SECRET_URI` | Secret | Key Vault URI of `clerk-secret-key` |
| `CLERK_WEBHOOK_SECRET_URI` | Secret | Key Vault URI of `clerk-webhook-secret` |
| `INTERNAL_SERVICE_TOKEN_SECRET_URI` | Secret | Key Vault URI of `internal-service-token` |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Variable | `pk_test_…` |
| `CLERK_ISSUER` | Variable | Clerk Frontend API URL |
| `CLERK_AUDIENCE` | Variable | Audience configured on the JWT template |
| `CLERK_AUTHORIZED_PARTIES` | Variable | `https://<web-app>.<region>.azurecontainerapps.io` |

`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is a **variable, not a secret**, and is a build argument rather than a runtime value: Clerk inlines it into the client bundle, so it must be present when the web image is built. `next build` fails without it, and the deploy workflow stops early with an explicit message rather than pushing a broken image.

### What each component receives

| Component | Receives | Why |
| --- | --- | --- |
| API container app | `CLERK_ISSUER`, `CLERK_AUDIENCE`, `CLERK_AUTHORIZED_PARTIES`, `INTERNAL_SERVICE_TOKEN` | Verifies tokens itself; never holds a Clerk client key. |
| Web container app | `CLERK_SECRET_KEY`, `CLERK_WEBHOOK_SECRET`, `INTERNAL_SERVICE_TOKEN` | Holds the browser session and is the only caller of the internal endpoint. |
| Web image build | `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Inlined into the client bundle at build time. |

If a Key Vault URI is left unset, that secret is simply omitted from the revision. With `CLERK_ISSUER` unset the API returns `503 authentication_unavailable` on every protected route, which is the intended fail-closed behaviour — not a misconfiguration to work around by loosening the check.

## Deployment order

Deploy in this order and keep the previous healthy revisions for rollback.

```bash
pnpm api:migrate
```

Then the API revision, then the web revision. The web application calls endpoints that will not exist until the API revision is live, so reversing the last two steps produces failing requests for the duration.

Confirm the API keeps internal ingress after deploying. It must never be publicly routable.

## Verifying a deployment

```bash
curl -fsS https://<web-host>/api/status
```

Expect `{"api":"available"}`.

Then, signed in as an invited member, confirm that Settings loads a profile and that the collection screen renders. A `503 authentication_unavailable` from the API means `CLERK_ISSUER` is unset on the API revision.

## Account deletion

Deletion is two-phase and recoverable.

| Phase | Actor | Effect |
| --- | --- | --- |
| 1 | Member, via Settings | ScentIQ marks the account `deletion_pending`; every endpoint but the rollback refuses it. |
| 2 | Next.js | Deletes the Clerk identity. On failure, rolls the pending mark back. |
| 3 | Clerk webhook | Signed `user.deleted` event drives the actual data removal. |

Data removal is idempotent by provider event id, so a retried webhook is a successful no-op.

### Reconciliation

If a webhook never arrives, the account stays `deletion_pending` and unusable. Run reconciliation on a schedule:

```bash
pnpm api:reconcile-deletions
```

Inspect first without changing anything:

```bash
pnpm api:reconcile-deletions -- --dry-run
```

Both print a JSON summary containing only identifiers — never email addresses or other personal data. The default grace period is 24 hours; override with `--grace-hours`.

## Troubleshooting

### Every request returns 401

Check the JWT template includes `email`. This is the most common cause on a new Clerk application. Also confirm `CLERK_AUDIENCE` matches the template and, if `CLERK_AUTHORIZED_PARTIES` is set, that the web origin is listed.

### Every request returns 503 `authentication_unavailable`

`CLERK_ISSUER` is missing on the API revision. Authentication fails closed rather than allowing traffic.

### A member reports being locked out with "This account is being deleted"

The account is `deletion_pending`. Either phase 2 failed without rolling back, or the webhook has not arrived. Confirm the intent with the member. To restore the account, clear `lifecycle_state` back to `active` and `deletion_requested_at` to `NULL`; to complete the deletion, let reconciliation run.

### The webhook returns 503 `not_configured`

One of `API_INTERNAL_URL`, `INTERNAL_SERVICE_TOKEN` or `CLERK_WEBHOOK_SECRET` is missing on the web revision. The route fails closed rather than accepting unverified events.

### The webhook returns 400 `invalid_signature`

`CLERK_WEBHOOK_SECRET` does not match the endpoint's signing secret in Clerk. Rotate it in Key Vault and redeploy the web revision. Request bodies are never logged, as they are unverified input.

### The webhook returns 500

Forwarding to the API failed. Clerk will retry, and processing is idempotent, so a transient failure is safe. Check API availability and that `INTERNAL_SERVICE_TOKEN` is identical on both revisions.

## Rotating the internal service credential

The web and API revisions must agree, so rotate with a brief overlap rather than atomically:

1. Update the Key Vault secret.
2. Deploy the API revision with the new value.
3. Deploy the web revision with the new value.

Between steps 2 and 3 the webhook returns `401` and Clerk retries. Because processing is idempotent, no event is lost.

## Telemetry

Logs exclude tokens, email addresses, free-text notes, purchase details and secrets. Provider error text is not echoed into responses or logs, as it can carry token material. When adding a log line, record identifiers and outcomes, not member content.
