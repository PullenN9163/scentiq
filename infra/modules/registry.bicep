param location string
param registryName string
param useExisting bool
param principalId string
param commonTags object

resource newRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = if (!useExisting) {
  name: registryName
  location: location
  tags: commonTags
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

resource existingRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}

resource existingRegistryTags 'Microsoft.Resources/tags@2025-04-01' = if (useExisting) {
  name: 'default'
  scope: existingRegistry
  properties: {
    tags: union(existingRegistry.tags, commonTags)
  }
}

resource acrPullNew 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!useExisting) {
  name: guid(newRegistry.id, principalId, 'AcrPull')
  scope: newRegistry
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  }
}

resource acrPullExisting 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (useExisting) {
  name: guid(existingRegistry.id, principalId, 'AcrPull')
  scope: existingRegistry
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  }
}

output id string = useExisting ? existingRegistry.id : newRegistry!.id
output loginServer string = useExisting ? existingRegistry.properties.loginServer : newRegistry!.properties.loginServer
