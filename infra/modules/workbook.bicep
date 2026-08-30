param location string
param environmentName string
param workspaceResourceId string
param applicationInsightsResourceId string
param containerEnvironmentResourceId string
param webAppResourceId string
param apiAppResourceId string
param migrationJobResourceId string
param postgresResourceId string
param commonTags object

var workbookTemplate = '''
{
  "version": "Notebook/1.0",
  "items": [
    {
      "type": 9,
      "content": {
        "version": "KqlParameterItem/1.0",
        "parameters": [
          { "id": "TimeRange", "name": "TimeRange", "type": 4, "isRequired": true, "value": { "durationMs": 86400000 } },
          { "id": "Environment", "name": "Environment", "type": 1, "isRequired": true, "value": "__environmentName__" },
          { "id": "ApplicationInsightsResourceId", "name": "ApplicationInsightsResourceId", "type": 1, "isRequired": true, "value": "__applicationInsightsResourceId__" },
          { "id": "ContainerEnvironmentResourceId", "name": "ContainerEnvironmentResourceId", "type": 1, "isRequired": true, "value": "__containerEnvironmentResourceId__" },
          { "id": "PostgresResourceId", "name": "PostgresResourceId", "type": 1, "isRequired": true, "value": "__postgresResourceId__" }
        ]
      },
      "name": "Observability parameters"
    },
    {
      "type": 3,
      "content": {
        "version": "KqlItem/1.0",
        "title": "Availability",
        "query": "AppAvailabilityResults | where _ResourceId == '{ApplicationInsightsResourceId}' | summarize AvailabilityPercent = round(100.0 * countif(Success == true) / count(), 2) by bin(TimeGenerated, 5m), TestName | order by TimeGenerated desc",
        "size": 0,
        "timeContext": { "durationMs": 86400000 }
      },
      "name": "Availability"
    },
    {
      "type": 3,
      "content": {
        "version": "KqlItem/1.0",
        "title": "Requests and failure percentage",
        "query": "AppRequests | where _ResourceId == '{ApplicationInsightsResourceId}' | extend EnvironmentTag = tostring(Properties['scentiq.environment']) | where EnvironmentTag == '{Environment}' | summarize RequestCount = count(), FailurePercent = round(100.0 * countif(Success == false) / count(), 2) by bin(TimeGenerated, 5m), AppRoleName | order by TimeGenerated desc",
        "size": 0,
        "timeContext": { "durationMs": 86400000 }
      },
      "name": "Requests"
    },
    {
      "type": 3,
      "content": {
        "version": "KqlItem/1.0",
        "title": "Request duration p50/p95",
        "query": "AppRequests | where _ResourceId == '{ApplicationInsightsResourceId}' | extend EnvironmentTag = tostring(Properties['scentiq.environment']) | where EnvironmentTag == '{Environment}' | summarize p50 = percentile(DurationMs, 50), p95 = percentile(DurationMs, 95) by bin(TimeGenerated, 5m), AppRoleName | order by TimeGenerated desc",
        "size": 0,
        "timeContext": { "durationMs": 86400000 }
      },
      "name": "Latency"
    },
    {
      "type": 3,
      "content": {
        "version": "KqlItem/1.0",
        "title": "Dependencies",
        "query": "AppDependencies | where _ResourceId == '{ApplicationInsightsResourceId}' | extend EnvironmentTag = tostring(Properties['scentiq.environment']) | where EnvironmentTag == '{Environment}' | summarize Calls = count(), Failures = countif(Success == false), p95 = percentile(DurationMs, 95) by Target, DependencyType | order by Failures desc, p95 desc",
        "size": 0,
        "timeContext": { "durationMs": 86400000 }
      },
      "name": "Dependencies"
    },
    {
      "type": 3,
      "content": {
        "version": "KqlItem/1.0",
        "title": "Exceptions",
        "query": "AppExceptions | where _ResourceId == '{ApplicationInsightsResourceId}' | extend EnvironmentTag = tostring(Properties['scentiq.environment']) | where EnvironmentTag == '{Environment}' | summarize ExceptionCount = count() by ProblemId, ExceptionType, bin(TimeGenerated, 5m) | order by TimeGenerated desc",
        "size": 0,
        "timeContext": { "durationMs": 86400000 }
      },
      "name": "Exceptions"
    },
    {
      "type": 3,
      "content": {
        "version": "KqlItem/1.0",
        "title": "Container Apps console logs",
        "query": "ContainerAppConsoleLogs_CL | where _ResourceId == '{ContainerEnvironmentResourceId}' | where ContainerAppName_s in ('scentiq-web-__environmentName__-eus', 'scentiq-api-__environmentName__-eus') | project TimeGenerated, ContainerAppName_s, RevisionName_s, Log_s | order by TimeGenerated desc | take 100",
        "size": 0,
        "timeContext": { "durationMs": 86400000 }
      },
      "name": "Container console"
    },
    {
      "type": 3,
      "content": {
        "version": "KqlItem/1.0",
        "title": "Container Apps system logs and migration executions",
        "query": "ContainerAppSystemLogs_CL | where _ResourceId == '{ContainerEnvironmentResourceId}' | where ContainerAppName_s in ('scentiq-web-__environmentName__-eus', 'scentiq-api-__environmentName__-eus', 'scentiq-migrate-__environmentName__-eus') | project TimeGenerated, ContainerAppName_s, RevisionName_s, Reason_s, Log_s | order by TimeGenerated desc | take 100",
        "size": 0,
        "timeContext": { "durationMs": 86400000 }
      },
      "name": "Container system"
    },
    {
      "type": 3,
      "content": {
        "version": "KqlItem/1.0",
        "title": "PostgreSQL saturation and storage",
        "query": "InsightsMetrics | where _ResourceId == '{PostgresResourceId}' | where Namespace == 'Microsoft.DBforPostgreSQL/flexibleServers' | where Name in ('cpu_percent', 'memory_percent', 'storage_percent', 'active_connections') | summarize AverageValue = avg(Val) by Name, bin(TimeGenerated, 5m) | order by TimeGenerated desc",
        "size": 0,
        "timeContext": { "durationMs": 86400000 }
      },
      "name": "PostgreSQL"
    },
    {
      "type": 3,
      "content": {
        "version": "KqlItem/1.0",
        "title": "Recent Azure Activity",
        "query": "AzureActivity | where ResourceId in ('__webAppResourceId__', '__apiAppResourceId__', '__migrationJobResourceId__', '{PostgresResourceId}') | project TimeGenerated, OperationNameValue, ActivityStatusValue, Level, ResourceId | order by TimeGenerated desc | take 100",
        "size": 0,
        "timeContext": { "durationMs": 86400000 }
      },
      "name": "Azure Activity"
    }
  ],
  "fallbackResourceIds": ["__workspaceResourceId__"]
}
'''

var workbookData = replace(replace(replace(replace(replace(replace(replace(replace(workbookTemplate, '__environmentName__', environmentName), '__applicationInsightsResourceId__', applicationInsightsResourceId), '__containerEnvironmentResourceId__', containerEnvironmentResourceId), '__postgresResourceId__', postgresResourceId), '__webAppResourceId__', webAppResourceId), '__apiAppResourceId__', apiAppResourceId), '__migrationJobResourceId__', migrationJobResourceId), '__workspaceResourceId__', workspaceResourceId)

resource workbook 'Microsoft.Insights/workbooks@2023-06-01' = {
  name: guid(resourceGroup().id, 'scentiq-observability-workbook-v1')
  location: location
  kind: 'shared'
  tags: commonTags
  properties: {
    category: 'workbook'
    displayName: 'ScentIQ development observability'
    serializedData: workbookData
    sourceId: workspaceResourceId
    version: '1.0'
  }
}

output workbookId string = workbook.id
