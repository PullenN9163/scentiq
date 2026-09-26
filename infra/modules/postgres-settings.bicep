param serverName string
param workspaceResourceId string
param enablePostgresLock bool
param allowAzureServicesFirewallRule bool
param azureServicesFirewallRuleName string

resource server 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' existing = {
  name: serverName
}

resource scentiqDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: server
  name: 'scentiq_dev'
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource requireSecureTransport 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2024-08-01' = {
  parent: server
  name: 'require_secure_transport'
  properties: {
    value: 'on'
    source: 'user-override'
  }
}

resource catalogExtensions 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2024-08-01' = {
  parent: server
  name: 'azure.extensions'
  properties: {
    value: 'PG_TRGM'
    source: 'user-override'
  }
}

resource azureServicesFirewallRule 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = if (allowAzureServicesFirewallRule) {
  parent: server
  name: azureServicesFirewallRuleName
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource postgresDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  scope: server
  name: 'scentiq-postgres-diagnostics'
  properties: {
    workspaceId: workspaceResourceId
    logAnalyticsDestinationType: 'Dedicated'
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

resource postgresLock 'Microsoft.Authorization/locks@2020-05-01' = if (enablePostgresLock) {
  scope: server
  name: 'scentiq-postgres-protection'
  properties: {
    level: 'CanNotDelete'
    notes: 'Protects ScentIQ PostgreSQL data. Follow the Azure recovery runbook before removing this lock.'
  }
}

output databaseName string = scentiqDatabase.name
