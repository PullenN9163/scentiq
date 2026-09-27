param location string
param registryName string
param useExisting bool
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

output id string = useExisting ? existingRegistry.id : newRegistry!.id
output loginServer string = useExisting ? existingRegistry.properties.loginServer : newRegistry!.properties.loginServer
