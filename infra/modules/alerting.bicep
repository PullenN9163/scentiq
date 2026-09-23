param location string
param environmentName string
param workspaceResourceId string
param applicationInsightsResourceId string
param actionGroupId string
param containerEnvironmentName string
param webAppName string
param apiAppName string
param migrationJobName string
param postgresServerName string
param postgresLocation string
param commonTags object

var runbookPath = 'docs/runbooks/azure-deployment.md#monitoring-alerts'
var workspaceScope = workspaceResourceId
var postgresScope = resourceId('Microsoft.DBforPostgreSQL/flexibleServers', postgresServerName)

// These extension resources use only categories returned by the read-only
// diagnosticSettingsCategories inventory. They do not PUT their parent resources.
resource containerEnvironment 'Microsoft.App/managedEnvironments@2025-01-01' existing = {
  name: containerEnvironmentName
}

resource webApp 'Microsoft.App/containerApps@2025-01-01' existing = {
  name: webAppName
}

resource apiApp 'Microsoft.App/containerApps@2025-01-01' existing = {
  name: apiAppName
}

resource migrationJob 'Microsoft.App/jobs@2025-01-01' existing = {
  name: migrationJobName
}

resource environmentDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'scentiq-container-environment-observability'
  scope: containerEnvironment
  properties: {
    workspaceId: workspaceResourceId
    logs: [
      { category: 'ContainerAppConsoleLogs', enabled: true }
      { category: 'ContainerAppSystemLogs', enabled: true }
      { category: 'ContainerAppHTTPLogs', enabled: true }
    ]
    metrics: [
      { category: 'AllMetrics', enabled: true }
    ]
  }
}

resource webMetricsDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'scentiq-web-metrics'
  scope: webApp
  properties: {
    workspaceId: workspaceResourceId
    logs: []
    metrics: [
      { category: 'AllMetrics', enabled: true }
    ]
  }
}

resource apiMetricsDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'scentiq-api-metrics'
  scope: apiApp
  properties: {
    workspaceId: workspaceResourceId
    logs: []
    metrics: [
      { category: 'AllMetrics', enabled: true }
    ]
  }
}

resource migrationDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'scentiq-migration-job-logs'
  scope: migrationJob
  properties: {
    workspaceId: workspaceResourceId
    logs: []
    metrics: [
      { category: 'Basic', enabled: true }
    ]
  }
}

resource availabilityAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: 'scentiq-availability-${environmentName}'
  location: location
  kind: 'LogAlert'
  tags: commonTags
  properties: {
    actions: {
      actionGroups: [actionGroupId]
    }
    autoMitigate: true
    criteria: {
      allOf: [
        {
          query: replace('''
AppAvailabilityResults
| where _ResourceId == '__applicationInsightsResourceId__'
| where Success == false
| summarize FailureCount = count() by bin(TimeGenerated, 5m)
| project TimeGenerated, FailureCount
''', '__applicationInsightsResourceId__', applicationInsightsResourceId)
          timeAggregation: 'Maximum'
          operator: 'GreaterThan'
          threshold: 0
          metricMeasureColumn: 'FailureCount'
          failingPeriods: {
            minFailingPeriodsToAlert: 2
            numberOfEvaluationPeriods: 2
          }
        }
      ]
    }
    description: 'Two consecutive failed ScentIQ availability evaluations. Runbook: ${runbookPath}'
    displayName: 'ScentIQ availability failures (${environmentName})'
    enabled: true
    evaluationFrequency: 'PT5M'
    scopes: [workspaceScope]
    severity: 1
    skipQueryValidation: true
    windowSize: 'PT5M'
  }
}

resource httpFailureRateAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: 'scentiq-http-failure-rate-${environmentName}'
  location: location
  kind: 'LogAlert'
  tags: commonTags
  properties: {
    actions: {
      actionGroups: [actionGroupId]
    }
    autoMitigate: true
    criteria: {
      allOf: [
        {
          query: replace('''
AppRequests
| where _ResourceId == '__applicationInsightsResourceId__'
| summarize RequestCount = count(), FailureRate = 100.0 * countif(Success == false) / count() by bin(TimeGenerated, 5m)
| where RequestCount >= 20
| project TimeGenerated, FailureRate
''', '__applicationInsightsResourceId__', applicationInsightsResourceId)
          timeAggregation: 'Maximum'
          operator: 'GreaterThan'
          threshold: 5
          metricMeasureColumn: 'FailureRate'
          failingPeriods: {
            minFailingPeriodsToAlert: 3
            numberOfEvaluationPeriods: 3
          }
        }
      ]
    }
    description: 'Sustained HTTP failure rate above five percent after a 20-request guard. Runbook: ${runbookPath}'
    displayName: 'ScentIQ HTTP failure rate (${environmentName})'
    enabled: true
    evaluationFrequency: 'PT5M'
    scopes: [workspaceScope]
    severity: 2
    skipQueryValidation: true
    windowSize: 'PT15M'
  }
}

resource latencyAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: 'scentiq-http-p95-latency-${environmentName}'
  location: location
  kind: 'LogAlert'
  tags: commonTags
  properties: {
    actions: {
      actionGroups: [actionGroupId]
    }
    autoMitigate: true
    criteria: {
      allOf: [
        {
          query: replace('''
AppRequests
| where _ResourceId == '__applicationInsightsResourceId__'
| summarize RequestCount = count(), P95DurationMs = percentile(DurationMs, 95) by bin(TimeGenerated, 5m)
| where RequestCount >= 20
| project TimeGenerated, P95DurationMs
''', '__applicationInsightsResourceId__', applicationInsightsResourceId)
          timeAggregation: 'Maximum'
          operator: 'GreaterThan'
          threshold: 2000
          metricMeasureColumn: 'P95DurationMs'
          failingPeriods: {
            minFailingPeriodsToAlert: 3
            numberOfEvaluationPeriods: 3
          }
        }
      ]
    }
    description: 'Sustained p95 HTTP duration above two seconds after a 20-request guard. Runbook: ${runbookPath}'
    displayName: 'ScentIQ HTTP p95 latency (${environmentName})'
    enabled: true
    evaluationFrequency: 'PT5M'
    scopes: [workspaceScope]
    severity: 2
    skipQueryValidation: true
    windowSize: 'PT15M'
  }
}

resource migrationFailureAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: 'scentiq-migration-failure-${environmentName}'
  location: location
  kind: 'LogAlert'
  tags: commonTags
  properties: {
    actions: {
      actionGroups: [actionGroupId]
    }
    autoMitigate: true
    criteria: {
      allOf: [
        {
          query: replace('''
union isfuzzy=true ContainerAppSystemLogs_CL, AzureDiagnostics
| where _ResourceId == '__migrationJobResourceId__'
| where tostring(Log_s) has_any ('Failed', 'TimedOut', 'Timeout')
| summarize MigrationFailureCount = count()
''', '__migrationJobResourceId__', migrationJob.id)
          timeAggregation: 'Maximum'
          operator: 'GreaterThan'
          threshold: 0
          metricMeasureColumn: 'MigrationFailureCount'
          failingPeriods: {
            minFailingPeriodsToAlert: 1
            numberOfEvaluationPeriods: 1
          }
        }
      ]
    }
    description: 'ScentIQ migration job failed or timed out. Runbook: ${runbookPath}'
    displayName: 'ScentIQ migration job failure (${environmentName})'
    enabled: true
    evaluationFrequency: 'PT5M'
    scopes: [workspaceScope]
    severity: 1
    skipQueryValidation: true
    windowSize: 'PT5M'
  }
}

resource postgresSaturationAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'scentiq-postgres-saturation-${environmentName}'
  location: 'global'
  tags: commonTags
  properties: {
    actions: [
      { actionGroupId: actionGroupId }
    ]
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'HighPostgresCpu'
          criterionType: 'StaticThresholdCriterion'
          metricName: 'cpu_percent'
          metricNamespace: 'Microsoft.DBforPostgreSQL/flexibleServers'
          operator: 'GreaterThan'
          threshold: 80
          timeAggregation: 'Average'
        }
      ]
    }
    description: 'PostgreSQL CPU saturation above 80 percent for 15 minutes. Runbook: ${runbookPath}'
    enabled: true
    evaluationFrequency: 'PT5M'
    scopes: [postgresScope]
    severity: 2
    targetResourceRegion: postgresLocation
    targetResourceType: 'Microsoft.DBforPostgreSQL/flexibleServers'
    windowSize: 'PT15M'
  }
}

resource postgresStorageAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'scentiq-postgres-storage-${environmentName}'
  location: 'global'
  tags: commonTags
  properties: {
    actions: [
      { actionGroupId: actionGroupId }
    ]
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'HighPostgresStorage'
          criterionType: 'StaticThresholdCriterion'
          metricName: 'storage_percent'
          metricNamespace: 'Microsoft.DBforPostgreSQL/flexibleServers'
          operator: 'GreaterThan'
          threshold: 80
          timeAggregation: 'Average'
        }
      ]
    }
    description: 'PostgreSQL storage capacity above 80 percent for 15 minutes. Runbook: ${runbookPath}'
    enabled: true
    evaluationFrequency: 'PT5M'
    scopes: [postgresScope]
    severity: 3
    targetResourceRegion: postgresLocation
    targetResourceType: 'Microsoft.DBforPostgreSQL/flexibleServers'
    windowSize: 'PT15M'
  }
}

resource resourceHealthAlert 'Microsoft.Insights/activityLogAlerts@2023-01-01-preview' = {
  name: 'scentiq-resource-health-${environmentName}'
  location: 'global'
  tags: commonTags
  properties: {
    actions: {
      actionGroups: [
        { actionGroupId: actionGroupId }
      ]
    }
    condition: {
      allOf: [
        { field: 'category', equals: 'ResourceHealth' }
        { field: 'properties.currentHealthStatus', containsAny: ['Unavailable', 'Degraded'] }
      ]
    }
    description: 'ScentIQ resource entered an unavailable or degraded health state. Runbook: ${runbookPath}'
    enabled: true
    scopes: [resourceGroup().id]
  }
}

resource serviceHealthAlert 'Microsoft.Insights/activityLogAlerts@2023-01-01-preview' = {
  name: 'scentiq-service-health-${environmentName}'
  location: 'global'
  tags: commonTags
  properties: {
    actions: {
      actionGroups: [
        { actionGroupId: actionGroupId }
      ]
    }
    condition: {
      allOf: [
        { field: 'category', equals: 'ServiceHealth' }
        { field: 'properties.incidentType', containsAny: ['Incident', 'Maintenance'] }
      ]
    }
    description: 'Azure service incident or planned maintenance affects ScentIQ. Runbook: ${runbookPath}'
    enabled: true
    scopes: [subscription().id]
  }
}

resource deploymentFailureAlert 'Microsoft.Insights/activityLogAlerts@2023-01-01-preview' = {
  name: 'scentiq-deployment-failure-${environmentName}'
  location: 'global'
  tags: commonTags
  properties: {
    actions: {
      actionGroups: [
        { actionGroupId: actionGroupId }
      ]
    }
    condition: {
      allOf: [
        { field: 'category', equals: 'Administrative' }
        { field: 'status', equals: 'Failed' }
        { field: 'operationName', equals: 'Microsoft.Resources/deployments/write' }
      ]
    }
    description: 'Azure Resource Manager deployment failed for the ScentIQ resource group. Runbook: ${runbookPath}'
    enabled: true
    scopes: [resourceGroup().id]
  }
}

output diagnosticSettingIds array = [
  environmentDiagnostics.id
  webMetricsDiagnostics.id
  apiMetricsDiagnostics.id
  migrationDiagnostics.id
]

output alertIds array = [
  availabilityAlert.id
  httpFailureRateAlert.id
  latencyAlert.id
  migrationFailureAlert.id
  postgresSaturationAlert.id
  postgresStorageAlert.id
  resourceHealthAlert.id
  serviceHealthAlert.id
  deploymentFailureAlert.id
]
