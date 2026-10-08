# Azure Development Deployment Runbook

ScentIQ deploys to `scentiq-rg-dev-eus` through modular Bicep and GitHub Actions. The development parameter file adopts the existing Log Analytics workspace, storage account, Key Vault, PostgreSQL Flexible Server, user-assigned identity, Container Apps environment, and their established role assignments. It creates the missing registry, Application Insights component, workloads, migration job, and ACR pull assignment. Fresh-environment mode creates the Blob and Key Vault assignments as part of the corresponding modules.

## Required GitHub environment configuration

Create a protected `development` environment with the non-secret variables `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and `AZURE_SUBSCRIPTION_ID`. Add `AZURE_ALERT_EMAILS` as a GitHub environment variable containing a comma-separated list of operational email receivers, such as `owner@example.com,oncall@example.com`; keep personal addresses out of the repository. Add `DATABASE_SECRET_URI` as an environment secret. Its value is the versionless Key Vault secret URI for the API PostgreSQL URL, such as `https://<vault>.vault.azure.net/secrets/database-url`. The referenced secret value must be a SQLAlchemy `postgresql+psycopg://` URL with TLS required. Do not store the URL itself in GitHub or the repository.

Configure a GitHub federated credential on the deployment identity for the protected environment. The subscription template bootstraps the custom `ScentIQ Subscription Deployment Runner` role for that identity. It grants only `Microsoft.Resources/deployments/*` and resource-group read at subscription scope; resource mutations remain limited by the identity's ScentIQ resource-group assignments. An owner must perform the initial subscription deployment. No client secret is used.

## Validate locally

```powershell
az bicep build --file infra/subscription.bicep
az bicep build-params --file infra/parameters/dev.bicepparam
if ([string]::IsNullOrWhiteSpace($env:SCENTIQ_ALERT_EMAIL)) {
  throw 'Set SCENTIQ_ALERT_EMAIL before Azure validation.'
}
$alertEmails = (@($env:SCENTIQ_ALERT_EMAIL) -join ',')
az deployment sub validate `
  --location eastus `
  --template-file infra/subscription.bicep `
  --parameters infra/parameters/dev.bicepparam `
  --parameters deployWorkloads=false alertEmails="$alertEmails" `
  --only-show-errors

az deployment sub what-if `
  --location eastus `
  --template-file infra/subscription.bicep `
  --parameters infra/parameters/dev.bicepparam `
  --parameters deployWorkloads=true alertEmails="$alertEmails" `
  --parameters databaseSecretUri='https://scentiq-kv-dev-eus.vault.azure.net/secrets/database-url'
```

Validation and What-If are read-only. Review the subscription-scope What-If before manually creating resources. The adoption parameter file must continue to name the known development resources exactly.

## Deployment sequence

The `Deploy development` workflow runs on `dev` and manual dispatch. It authenticates with OIDC, validates and deploys shared infrastructure through the subscription-scope entry point, builds API and web images tagged with the immutable Git commit SHA, and pushes them to ACR. It then deploys and executes the manual migration job. Application revisions are deployed only after that execution reports `Succeeded`. Completed development work is promoted from `dev` to protected `main` through a pull request.

The API has internal ingress. The public web app calls it over the Container Apps environment, so the deployment smoke test uses the web root and same-origin `/api/status` route. Routine application startup never applies migrations.

## Observe and recover

```powershell
az containerapp revision list --name scentiq-api-dev-eus --resource-group scentiq-rg-dev-eus --output table
az containerapp revision list --name scentiq-web-dev-eus --resource-group scentiq-rg-dev-eus --output table
az containerapp job execution list --name scentiq-migrate-dev-eus --resource-group scentiq-rg-dev-eus --output table
```

If migration fails, the workflow stops before application rollout. Correct the migration or connectivity issue and rerun the workflow. Do not bypass the gate. If a new application revision is unhealthy after a successful migration, reactivate the last known healthy immutable image, then inspect sanitized Application Insights traces and Container Apps logs. Database downgrades require a separately reviewed recovery decision; they are never automatic.

## Monitoring alerts

ScentIQ alert rules route availability, HTTP failure rate, p95 latency, migration failures, PostgreSQL saturation and storage, Resource Health, Service Health, and deployment failures to the managed operations action group. Treat a severity-1 alert as an immediate rollout or availability incident; severity 2 requires same-day investigation, and severity 3 capacity warnings require a planned response before the next deployment.

Start by opening the ScentIQ development observability workbook and checking the affected resource ID, time range, availability result, request volume, error percentage, and p95 duration. Console and system logs must be inspected only for operational fields; do not copy request bodies, headers, cookies, connection strings, or database URLs into tickets or chat. For a migration failure, retain the failed execution status, correct the migration or connectivity issue, and rerun the gated deployment. For Resource Health or Service Health, confirm the Azure incident scope before changing ScentIQ resources. Cost-budget notifications use the same action group and should trigger a review of replica floors, retention, and other approved cost controls rather than an unreviewed service shutdown.
