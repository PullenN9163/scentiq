param location string
param vaultName string
param useExisting bool
param commonTags object

resource newVault 'Microsoft.KeyVault/vaults@2023-07-01' = if (!useExisting) {
  name: vaultName
  location: location
  tags: commonTags
  properties: {
    tenantId: tenant().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
  }
}

resource existingVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: vaultName
}

resource existingVaultTags 'Microsoft.Resources/tags@2025-04-01' = if (useExisting) {
  name: 'default'
  scope: existingVault
  properties: {
    tags: union(existingVault.tags, commonTags)
  }
}

output id string = useExisting ? existingVault!.id : newVault!.id
output uri string = useExisting ? existingVault!.properties.vaultUri : newVault!.properties.vaultUri
