param location string
param workspaceName string
param applicationInsightsName string
param workspaceExistingTags object
param commonTags object
@allowed(['0.1', '0.5'])
param logDailyQuotaGb string = '0.1'
@minValue(31)
@maxValue(31)
param logRetentionDays int = 31

// Read-only inventory (2026-08-30) established the only writable properties
// below. The explicit tag contract prevents this adopted parent PUT from
// clearing tags that predate Bicep management.
resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: workspaceName
  location: location
  tags: union(workspaceExistingTags, commonTags)
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: logRetentionDays
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    workspaceCapping: {
      dailyQuotaGb: json(logDailyQuotaGb)
    }
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: applicationInsightsName
  location: location
  tags: commonTags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspace.id
    IngestionMode: 'LogAnalytics'
    // Application Insights accepts its own discrete retention settings. Keep
    // the supported 90-day default; workspace retention is configured above.
    RetentionInDays: 90
    DisableIpMasking: false
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

output workspaceResourceId string = workspace.id
output applicationInsightsResourceId string = insights.id
@secure()
output applicationInsightsConnectionString string = insights.properties.ConnectionString
