# Azure Storage and Key Vault Recovery Runbook

This runbook covers recovery actions for the ScentIQ Azure Storage account and Key Vault. Run every command with an identity that has the required Azure RBAC permissions. Use explicit resource names, review the target before changing it, and do not use storage keys, connection strings, or secret values.

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
az storage container list --account-name $storageAccountName --include-deleted --auth-mode login --query "[?name=='$containerName'].{name:name,version:version,deleted:deleted}" -o table
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

Disable the explicitly selected newer version, then confirm only the resolved version identifier:

```powershell
$newerVersionId = '<newer-secret-version-id>'
az keyvault secret set-attributes --id $newerVersionId --enabled false --only-show-errors -o none
az keyvault secret show --vault-name $keyVaultName --name $secretName --query id -o tsv
```

Re-enable the version if the rollback needs to be reversed:

```powershell
az keyvault secret set-attributes --id $newerVersionId --enabled true --only-show-errors -o none
```

## Controlled lock removal and reapplication

Only remove a `CanNotDelete` lock for a planned, approved recovery or maintenance operation. Record the resource, operator, change reference, and planned reapplication time before removal. Reapply the same lock immediately after the operation and verify it is present.

```powershell
$resourceGroupName = '<resource-group-name>'
$storageAccountName = '<storage-account-name>'
$keyVaultName = '<key-vault-name>'

az lock delete --name 'scentiq-storage-protection' --resource-group $resourceGroupName --resource-name $storageAccountName --resource-type 'Microsoft.Storage/storageAccounts'
az lock delete --name 'scentiq-key-vault-protection' --resource-group $resourceGroupName --resource-name $keyVaultName --resource-type 'Microsoft.KeyVault/vaults'

az lock create --name 'scentiq-storage-protection' --lock-type CanNotDelete --resource-group $resourceGroupName --resource-name $storageAccountName --resource-type 'Microsoft.Storage/storageAccounts' --notes 'Protects ScentIQ storage data. Follow the Azure recovery runbook before removing this lock.'
az lock create --name 'scentiq-key-vault-protection' --lock-type CanNotDelete --resource-group $resourceGroupName --resource-name $keyVaultName --resource-type 'Microsoft.KeyVault/vaults' --notes 'Protects ScentIQ Key Vault. Follow the Azure recovery runbook before removing this lock.'

az lock list --resource-group $resourceGroupName --resource-name $storageAccountName --resource-type 'Microsoft.Storage/storageAccounts' --query "[].{name:name,level:level}" -o table
az lock list --resource-group $resourceGroupName --resource-name $keyVaultName --resource-type 'Microsoft.KeyVault/vaults' --query "[].{name:name,level:level}" -o table
```
