param location string
param workspaceName string
param applicationInsightsName string
param useExistingWorkspace bool

resource newWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = if (!useExistingWorkspace) {
  name: workspaceName
  location: location
  properties: {
    retentionInDays: 30
    features: { enableLogAccessUsingOnlyResourcePermissions: true }
  }
}

resource existingWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = if (useExistingWorkspace) {
  name: workspaceName
}

var workspaceId = useExistingWorkspace ? existingWorkspace.id : newWorkspace.id

resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: applicationInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspaceId
    IngestionMode: 'LogAnalytics'
  }
}

output workspaceResourceId string = workspaceId
@secure()
output applicationInsightsConnectionString string = insights.properties.ConnectionString
