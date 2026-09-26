# Runbook: Calendar and Weather Integrations

Operational procedures for the Open-Meteo forecast and the Google and Outlook calendar connections.

## Prerequisites

- The database is migrated to `20260928_0006` or later.
- Identity is configured (see the [identity and accounts runbook](identity-and-accounts.md)). Every calendar and weather endpoint needs a signed-in member.
- Outbound HTTPS from the API container to the provider hosts listed below is allowed.

## Weather (Open-Meteo)

Weather needs no setup. With `WEATHER_API_BASE_URL`, `GEOCODING_API_BASE_URL` and `OPEN_METEO_API_KEY` blank, the API uses the free endpoints:

- `api.open-meteo.com`;
- `geocoding-api.open-meteo.com`.

The free tier is for **non-commercial use**. Before any commercial launch, buy an Open-Meteo plan and set:

| Setting | Value |
| --- | --- |
| `WEATHER_API_BASE_URL` | `https://customer-api.open-meteo.com` |
| `GEOCODING_API_BASE_URL` | `https://customer-geocoding-api.open-meteo.com` |
| `OPEN_METEO_API_KEY` | The plan's key, as a Key Vault-backed secret |

Settings shows Open-Meteo attribution next to the resolved location. Keep it.

### Troubleshooting weather

| Symptom | Cause |
| --- | --- |
| Today says "Add your location" | The member has no saved location (`409 location_required`). |
| Today says it couldn't find the location | The saved text never matched a place (`409 location_unresolved`). Ask the member to try "City, Country". |
| "Showing the last forecast we fetched" | Open-Meteo is unreachable. A cached forecast is being served with `stale: true`. |
| "The forecast is unavailable right now" | Open-Meteo is unreachable and nothing is cached (`503 weather_unavailable`). Check egress from the API container. |

## Calendar connections

The API runs the OAuth flows and holds the client secrets. The browser only sees provider consent pages and ScentIQ's own URLs. Every provider redirects back to:

```
<PUBLIC_APP_URL>/integrations/calendar/<provider>/callback
```

`PUBLIC_APP_URL` is the web app's origin:

- **Locally**, it is `http://localhost:3000`.
- **In Azure**, Bicep sets it to the web app's FQDN.

A provider shows as **Unavailable** in Settings until all of these are set:

- its client ID;
- its client secret;
- `PUBLIC_APP_URL`;
- `INTEGRATION_TOKEN_ENCRYPTION_KEY`.

### Refresh-token encryption key

Refresh tokens are sealed with AES-256-GCM before they are stored, and access tokens are never stored. Generate a key once per environment:

```bash
python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"
az keyvault secret set --vault-name "$vault" --name integration-token-encryption-key --value "<base64 key>"
```

**Losing the key disconnects every member.** Their tokens become unreadable, and each connection shows *Reconnect needed* on its next sync. Nothing else is affected.

**Rotation:**

1. Put the new key in `INTEGRATION_TOKEN_ENCRYPTION_KEY`.
2. Move the old key into `INTEGRATION_TOKEN_PREVIOUS_KEYS` (comma-separated).
3. Wait. Each connection is re-sealed with the new key on its next sync.
4. Remove the old key after a few weeks. Connections that never synced in that time then need reconnecting.

`INTEGRATION_TOKEN_PREVIOUS_KEYS` is not yet templated in Bicep. To rotate in Azure, add it to the API container app as an extra Key Vault-backed secret for the rotation window.

### Google Calendar

1. In Google Cloud Console, create or choose a project and enable the **Google Calendar API**.
2. Configure the **OAuth consent screen**:
   - Set the user type to External.
   - Add the scopes `openid`, `email` and `https://www.googleapis.com/auth/calendar.readonly`.
   - Leave publishing status on **Testing** for the private beta, and add each member's Google account as a test user. Testing allows up to 100.
3. Create an **OAuth client ID** of type *Web application*, with these authorized redirect URIs:
   - `http://localhost:3000/integrations/calendar/google/callback`;
   - `https://<web-fqdn>/integrations/calendar/google/callback`.
4. Record the client ID and secret. Store the secret in Key Vault as `google-oauth-client-secret`.

**Grant expiry in Testing mode.** Google expires refresh tokens after **7 days** while the consent screen is in Testing. Beta members will see *Reconnect needed* weekly until the app is published.

**Publishing.** `calendar.readonly` is a *sensitive* scope, so publishing requires Google's verification: a privacy policy, a homepage and a demo video.

### Outlook Calendar (Microsoft Entra ID)

This uses the `common` endpoint, so it works with work, school and personal (outlook.com) accounts. Microsoft has no per-grant revocation endpoint, so **Disconnect** deletes the stored grant; members can also remove ScentIQ at `https://myapps.microsoft.com` (work accounts) or `https://account.live.com/consent/Manage` (personal accounts).

1. In Entra ID, go to **App registrations → New registration**.
   - Supported account types: *Accounts in any organizational directory and personal Microsoft accounts*.
   - Redirect URI (Web): the callback URL above, with `microsoft` as the provider.
2. Under **API permissions**, add the Microsoft Graph delegated permissions `openid`, `email`, `offline_access`, `User.Read` and `Calendars.Read`.
3. Under **Certificates & secrets**, create a client secret.
   - Store it as `microsoft-oauth-client-secret`.
   - Put a reminder in the calendar before it expires. Microsoft secrets last at most 24 months.

### Azure configuration

Add these to the GitHub **`development` environment**:

| Name | Kind | Value |
| --- | --- | --- |
| `GOOGLE_OAUTH_CLIENT_ID` | Variable | Google OAuth client ID |
| `GOOGLE_OAUTH_CLIENT_SECRET_SECRET_URI` | Secret | Key Vault URI of `google-oauth-client-secret` |
| `MICROSOFT_OAUTH_CLIENT_ID` | Variable | Entra application (client) ID |
| `MICROSOFT_OAUTH_CLIENT_SECRET_SECRET_URI` | Secret | Key Vault URI of `microsoft-oauth-client-secret` |
| `INTEGRATION_TOKEN_ENCRYPTION_KEY_SECRET_URI` | Secret | Key Vault URI of `integration-token-encryption-key` |

Only the API container receives these. An empty URI omits that secret from the revision, which leaves the provider unavailable instead of misconfigured.

### Local development

1. Set these in your shell or `.env`:
   - `PUBLIC_APP_URL=http://localhost:3000`;
   - the Google client ID and secret;
   - a generated `INTEGRATION_TOKEN_ENCRYPTION_KEY`.
2. Restart the API.
3. Open Settings and choose **Connect Google Calendar** or **Connect Outlook Calendar**.

### How sync behaves

- **When it runs.** Events sync when they are read (Today, and later My Week), at most every 15 minutes per connection. **Sync now** in Settings forces a sync.
- **The window.** Each sync covers yesterday through 21 days ahead.
- **Which calendars.** Only calendars ticked in Settings are fetched. The main calendar starts ticked; shared and holiday calendars are opt-in.
- **What is stored.** Title, start, end, the all-day flag, location, and a derived occasion (work, dinner, gym and so on). Descriptions, attendees and meeting links are never stored.
- **Account deletion.** Deleting a member deletes their connections, calendars and events through `ON DELETE CASCADE`.

### Troubleshooting calendars

| Symptom | Cause |
| --- | --- |
| Provider shows **Unavailable** | A client ID or secret, `PUBLIC_APP_URL` or the encryption key is missing on the API revision. |
| `redirect_uri_mismatch` on Google's page | The callback URL isn't registered exactly: scheme, host and path must match. |
| "That connection request expired" | More than 10 minutes passed on the consent page, or the tab was reused. Connect again. |
| "Calendar access wasn't allowed" | The member unticked the calendar permission on Google's granular consent screen. |
| **Reconnect needed** | The grant was revoked or expired (weekly in Google's Testing mode), or the encryption key changed. The member reconnects from Settings; their calendar choices are kept. |
| "the last sync failed" | The provider was unreachable or rate-limited. Saved events are still shown, and the next read retries. |
