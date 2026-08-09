param location string
param vaultName string
param useExisting bool
param principalId string

resource newVault 'Microsoft.KeyVault/vaults@2023-07-01' = if (!useExisting) {
  name: vaultName
  location: location
  properties: {
    tenantId: tenant().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
  }
}

resource existingVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = if (useExisting) {
  name: vaultName
}

resource secretRoleNew 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!useExisting) {
  name: guid(newVault.id, principalId, 'Key Vault Secrets User')
  scope: newVault
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
  }
}

output id string = useExisting ? existingVault!.id : newVault!.id
output uri string = useExisting ? existingVault!.properties.vaultUri : newVault!.properties.vaultUri
