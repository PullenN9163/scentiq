param location string
param environmentName string
param useExisting bool
param workspaceResourceId string

resource newEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' = if (!useExisting) {
  name: environmentName
  location: location
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

resource existingEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' existing = if (useExisting) {
  name: environmentName
}

output id string = useExisting ? existingEnvironment.id : newEnvironment.id
