param location string
param environmentName string
param useExisting bool
param workspaceResourceId string
param commonTags object

resource newEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' = if (!useExisting) {
  name: environmentName
  location: location
  tags: commonTags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: reference(workspaceResourceId, '2023-09-01').customerId
        sharedKey: listKeys(workspaceResourceId, '2023-09-01').primarySharedKey
      }
    }
    zoneRedundant: false
  }
}

resource existingEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' existing = {
  name: environmentName
}

resource existingEnvironmentTags 'Microsoft.Resources/tags@2025-04-01' = if (useExisting) {
  name: 'default'
  scope: existingEnvironment
  properties: {
    tags: union(existingEnvironment.tags, commonTags)
  }
}

output id string = useExisting ? existingEnvironment.id : newEnvironment.id
output defaultDomain string = useExisting
  ? existingEnvironment.properties.defaultDomain
  : newEnvironment!.properties.defaultDomain
