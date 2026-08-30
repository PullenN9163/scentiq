# Azure Recovery Runbook

This runbook covers recovery actions for ScentIQ Azure Storage, Key Vault, and PostgreSQL Flexible Server. Run every command with an identity that has the required Azure RBAC permissions. Use explicit resource names, review the target before changing it, and do not use storage keys, connection strings, database passwords, or secret values.

## Staged security adoption

The infrastructure model has secure defaults: Shared Key authentication is disabled and Storage and Key Vault have `CanNotDelete` locks. The development adoption parameters deliberately keep `enableStorageSharedKeyAccess` enabled and `enableFoundationLocks` disabled until the API identity integration test and a recovery rehearsal are complete.

Deploy the recovery settings and all non-Shared-Key changes first. Confirm identity access without a key:

```powershell
az storage container list --account-name <storage-account-name> --auth-mode login --query "[].name" -o tsv
```

After the API identity integration test passes, set `enableStorageSharedKeyAccess` to `false`, validate and review the what-if, then deploy. Confirm the identity-authorized list still succeeds and that a separately authorized Shared-Key request is rejected; never retrieve or print a key to perform that test. Enable `enableFoundationLocks` only after the lock-removal and reapplication procedure below has been rehearsed.

Until those controls are enabled, a compromised Shared Key can bypass the preferred identity path and resource deletion remains less protected. Enabling a lock can delay intentional teardown or some replacement operations; use the controlled lock procedure rather than removing a lock speculatively.

Azure automatically garbage-collects uncommitted block lists after seven days. The managed lifecycle policy therefore deletes only `exports/temporary/` blobs after seven days; it does not apply a broad committed-blob deletion rule that could remove `uploads` or `system` data.

## Blob list, download, and version restore

Set the target names in the current PowerShell session. These values are resource identifiers, not credentials.

```powershell
$storageAccountName = '<storage-account-name>'
$containerName = '<container-name>'
$blobName = '<blob-name>'
$versionId = '<version-id>'
```

List Blob names and versions through Azure AD:

```powershell
az storage blob list --account-name $storageAccountName --container-name $containerName --include v --auth-mode login --query "[].{name:name,versionId:versionId,isCurrentVersion:isCurrentVersion}" -o table
```

Download an identified version to an operator-controlled local path for inspection. Do not redirect the content to a shared terminal or log.

```powershell
az storage blob download --account-name $storageAccountName --container-name $containerName --name $blobName --version-id $versionId --auth-mode login --file '<local-recovery-path>'
```

Restore a prior version by copying that version onto the current blob name. Confirm the source version and destination name before running this write operation.

```powershell
$sourceUri = "https://$storageAccountName.blob.core.windows.net/$containerName/$blobName?versionId=$versionId"
az storage blob copy start --account-name $storageAccountName --destination-container $containerName --destination-blob $blobName --source-uri $sourceUri --auth-mode login
```

## Soft-deleted container recovery

List deleted container versions first and select the exact deleted version to restore:

```powershell
$storageAccountName = '<storage-account-name>'
$containerName = '<container-name>'
az storage container list --account-name $storageAccountName --prefix $containerName --include-deleted --auth-mode login --query "[?name=='$containerName' && deleted==``true``].{name:name,version:version,deleted:deleted}" -o table
```

Restore only the selected deleted version:

```powershell
$deletedContainerVersion = '<deleted-container-version>'
az storage container restore --account-name $storageAccountName --name $containerName --deleted-version $deletedContainerVersion --auth-mode login
```

## Key Vault secret-version rollback

Secret values must not be displayed, copied into a command line, or added to a deployment parameter file. To revert resolution to an earlier enabled version, disable the newer version or versions after first recording their version identifiers. This preserves the older value without reading it.

```powershell
$keyVaultName = '<key-vault-name>'
$secretName = '<secret-name>'
az keyvault secret list-versions --vault-name $keyVaultName --name $secretName --query "[].{id:id,enabled:attributes.enabled,created:attributes.created}" -o table
```

Disable the explicitly selected newer version, then confirm enabled version metadata without retrieving any secret value:

```powershell
$newerVersionId = '<newer-secret-version-id>'
az keyvault secret set-attributes --id $newerVersionId --enabled false --only-show-errors -o none
az keyvault secret list-versions --vault-name $keyVaultName --name $secretName --query "[?attributes.enabled==``true``].{id:id,enabled:attributes.enabled,created:attributes.created}" -o table
```

Re-enable the version if the rollback needs to be reversed:

```powershell
az keyvault secret set-attributes --id $newerVersionId --enabled true --only-show-errors -o none
```

## PostgreSQL point-in-time restore drill

Use a point-in-time restore (PITR) to create a separate recovery server; it does not overwrite the source server. The production or development source resource group is allowed only as the source. Restore targets must be created in the explicit test resource group `scentiq-rg-test-eus` and must start with `scentiq-pg-restore-`.

First select a UTC restore point within the source server's retention window. Inspect server metadata and database names without printing credentials:

```powershell
$sourceResourceGroupName = '<source-resource-group-name>'
$sourceServerName = 'scentiq-pg-dev-eus'
$targetResourceGroupName = 'scentiq-rg-test-eus'
$restoreServerName = 'scentiq-pg-restore-<approved-drill-id>'
$restorePoint = '<UTC ISO 8601 timestamp, for example 2026-08-29T00:00:00Z>'
$expectedDatabaseName = 'scentiq_dev'

az postgres flexible-server show --resource-group $sourceResourceGroupName --name $sourceServerName --query "{id:id,state:state,earliestRestoreDate:backup.earliestRestoreDate}" -o json
az postgres flexible-server db list --resource-group $sourceResourceGroupName --server-name $sourceServerName --query "[].name" -o tsv
```

The guarded drill script is the only approved PostgreSQL restore and cleanup path. It resolves the source and resource-group IDs, requires the source to be `Ready`, reads `backup.earliestRestoreDate`, rejects future and out-of-window restore points, confirms that the target is absent, and does not retrieve a database password.

Run the read-only preflight first. It performs every source, retention-window, and target-absence check but does not create or change a server:

```powershell
.\scripts\azure\Test-PostgresRestore.ps1 `
  -ResourceGroupName $sourceResourceGroupName `
  -ServerName $sourceServerName `
  -RestoreServerName $restoreServerName `
  -RestorePoint $restorePoint `
  -ExpectedDatabaseName $expectedDatabaseName `
  -TargetResourceGroupName $targetResourceGroupName `
  -PreflightOnly
```

After the incident owner approves the preflight result, rerun the same guarded command without `-PreflightOnly`. The script creates the separate target, waits for `Ready`, and confirms that the expected database exists.

```powershell
.\scripts\azure\Test-PostgresRestore.ps1 `
  -ResourceGroupName $sourceResourceGroupName `
  -ServerName $sourceServerName `
  -RestoreServerName $restoreServerName `
  -RestorePoint $restorePoint `
  -ExpectedDatabaseName $expectedDatabaseName `
  -TargetResourceGroupName $targetResourceGroupName
```

Do not point an application at the restored server until an incident owner has approved the data and access validation. After successful normal verification, the script prints this exact guarded cleanup command. Run it separately only after approval. Cleanup rechecks `Ready` and the expected database before deletion; both `-CleanupOnly` and `-DeleteAfterVerification` are required confirmations.

```powershell
.\scripts\azure\Test-PostgresRestore.ps1 `
  -ResourceGroupName $sourceResourceGroupName `
  -ServerName $sourceServerName `
  -RestoreServerName $restoreServerName `
  -RestorePoint $restorePoint `
  -ExpectedDatabaseName $expectedDatabaseName `
  -TargetResourceGroupName $targetResourceGroupName `
  -CleanupOnly `
  -DeleteAfterVerification
```

## Controlled lock removal and reapplication

Only remove a `CanNotDelete` lock for a planned, approved recovery or maintenance operation. Record the resource, operator, change reference, and planned reapplication time before removal. Reapply the same lock immediately after the operation and verify it is present.

```powershell
$resourceGroupName = '<resource-group-name>'
$storageAccountName = '<storage-account-name>'
$keyVaultName = '<key-vault-name>'
$postgresServerName = 'scentiq-pg-dev-eus'

az lock delete --name 'scentiq-storage-protection' --resource-group $resourceGroupName --resource-name $storageAccountName --resource-type 'Microsoft.Storage/storageAccounts'
az lock delete --name 'scentiq-key-vault-protection' --resource-group $resourceGroupName --resource-name $keyVaultName --resource-type 'Microsoft.KeyVault/vaults'
az lock delete --name 'scentiq-postgres-protection' --resource-group $resourceGroupName --resource-name $postgresServerName --resource-type 'Microsoft.DBforPostgreSQL/flexibleServers'

az lock create --name 'scentiq-storage-protection' --lock-type CanNotDelete --resource-group $resourceGroupName --resource-name $storageAccountName --resource-type 'Microsoft.Storage/storageAccounts' --notes 'Protects ScentIQ storage data. Follow the Azure recovery runbook before removing this lock.'
az lock create --name 'scentiq-key-vault-protection' --lock-type CanNotDelete --resource-group $resourceGroupName --resource-name $keyVaultName --resource-type 'Microsoft.KeyVault/vaults' --notes 'Protects ScentIQ Key Vault. Follow the Azure recovery runbook before removing this lock.'
az lock create --name 'scentiq-postgres-protection' --lock-type CanNotDelete --resource-group $resourceGroupName --resource-name $postgresServerName --resource-type 'Microsoft.DBforPostgreSQL/flexibleServers' --notes 'Protects ScentIQ PostgreSQL data. Follow the Azure recovery runbook before removing this lock.'

az lock list --resource-group $resourceGroupName --resource-name $storageAccountName --resource-type 'Microsoft.Storage/storageAccounts' --query "[].{name:name,level:level}" -o table
az lock list --resource-group $resourceGroupName --resource-name $keyVaultName --resource-type 'Microsoft.KeyVault/vaults' --query "[].{name:name,level:level}" -o table
az lock list --resource-group $resourceGroupName --resource-name $postgresServerName --resource-type 'Microsoft.DBforPostgreSQL/flexibleServers' --query "[].{name:name,level:level}" -o table
```
