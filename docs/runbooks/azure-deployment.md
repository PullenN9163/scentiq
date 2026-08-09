# Azure Development Deployment Runbook

ScentIQ deploys to `scentiq-rg-dev-eus` through modular Bicep and GitHub Actions. The development parameter file adopts the existing Log Analytics workspace, storage account, Key Vault, PostgreSQL Flexible Server, user-assigned identity, Container Apps environment, and their established role assignments. It creates the missing registry, Application Insights component, workloads, migration job, and ACR pull assignment. Fresh-environment mode creates the Blob and Key Vault assignments as part of the corresponding modules.

## Required GitHub environment configuration

Create a protected `development` environment with the non-secret variables `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and `AZURE_SUBSCRIPTION_ID`. Add `DATABASE_SECRET_URI` as an environment secret. Its value is the versionless Key Vault secret URI for the API PostgreSQL URL, such as `https://<vault>.vault.azure.net/secrets/database-url`. The referenced secret value must be a SQLAlchemy `postgresql+psycopg://` URL with TLS required. Do not store the URL itself in GitHub or the repository.

Configure a GitHub federated credential on the deployment identity for the protected environment. Grant that identity only the resource-group deployment and role-assignment permissions required by the template. No client secret is used.

## Validate locally

```powershell
az bicep build --file infra/main.bicep
az bicep build-params --file infra/parameters/dev.bicepparam
az deployment group validate `
  --resource-group scentiq-rg-dev-eus `
  --template-file infra/main.bicep `
  --parameters infra/parameters/dev.bicepparam `
  --parameters deployWorkloads=false `
  --only-show-errors
```

Validation is read-only. Review `az deployment group what-if` before manually creating resources. The adoption parameter file must continue to name the known development resources exactly.

## Deployment sequence

The `Deploy development` workflow runs on `main` and manual dispatch. It authenticates with OIDC, validates and deploys shared infrastructure, builds API and web images tagged with the immutable Git commit SHA, and pushes them to ACR. It then deploys and executes the manual migration job. Application revisions are deployed only after that execution reports `Succeeded`.

The API has internal ingress. The public web app calls it over the Container Apps environment, so the deployment smoke test uses the web root and same-origin `/api/status` route. Routine application startup never applies migrations.

## Observe and recover

```powershell
az containerapp revision list --name scentiq-api-dev-eus --resource-group scentiq-rg-dev-eus --output table
az containerapp revision list --name scentiq-web-dev-eus --resource-group scentiq-rg-dev-eus --output table
az containerapp job execution list --name scentiq-migrate-dev-eus --resource-group scentiq-rg-dev-eus --output table
```

If migration fails, the workflow stops before application rollout. Correct the migration or connectivity issue and rerun the workflow. Do not bypass the gate. If a new application revision is unhealthy after a successful migration, reactivate the last known healthy immutable image, then inspect sanitized Application Insights traces and Container Apps logs. Database downgrades require a separately reviewed recovery decision; they are never automatic.
