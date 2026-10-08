param location string
param serverName string
param useExisting bool
param administratorLogin string = 'scentiqadmin'
@secure()
param administratorPassword string = ''
param skuName string = 'Standard_B1ms'
param tenantId string
param workspaceResourceId string
param enablePostgresLock bool = true
param allowAzureServicesFirewallRule bool = false
param azureServicesFirewallRuleName string
param existingTags object
param commonTags object

module freshServer 'postgres-fresh-server.bicep' = if (!useExisting) {
  name: 'postgres-fresh-server'
  params: {
    location: location
    serverName: serverName
    administratorLogin: administratorLogin
    administratorPassword: administratorPassword
    skuName: skuName
    tenantId: tenantId
    commonTags: commonTags
  }
}

// The adopted path models every observed writable, reset-sensitive field without
// supplying create-only administrator credentials or changing its identity.
resource adoptedServer 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = if (useExisting) {
  name: serverName
  location: location
  // Bicep cannot evaluate an existing resource's tags before this parent PUT.
  // The caller therefore supplies the redacted, read-only inventory as an
  // explicit contract so the PUT cannot clear unrelated live tags.
  tags: union(existingTags, commonTags)
  sku: {
    name: skuName
    tier: 'Burstable'
  }
  properties: {
    version: '18'
    storage: {
      storageSizeGB: 32
      autoGrow: 'Enabled'
      iops: 120
      tier: 'P4'
      type: 'Premium_LRS'
    }
    authConfig: {
      activeDirectoryAuth: 'Enabled'
      passwordAuth: 'Enabled'
      tenantId: tenantId
    }
    dataEncryption: {
      type: 'SystemManaged'
    }
    backup: {
      backupRetentionDays: 14
      geoRedundantBackup: 'Disabled'
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
    maintenanceWindow: {
      customWindow: 'Enabled'
      dayOfWeek: 0
      startHour: 7
      startMinute: 0
    }
    replicationRole: 'Primary'
    replica: {
      role: 'Primary'
    }
  }
}

module postgresSettings 'postgres-settings.bicep' = {
  name: 'postgres-settings'
  params: {
    serverName: serverName
    workspaceResourceId: workspaceResourceId
    enablePostgresLock: enablePostgresLock
    allowAzureServicesFirewallRule: allowAzureServicesFirewallRule
    azureServicesFirewallRuleName: azureServicesFirewallRuleName
  }
  dependsOn: [
    freshServer
    adoptedServer
  ]
}

output id string = useExisting ? adoptedServer!.id : freshServer!.outputs.id
output fqdn string = useExisting ? adoptedServer!.properties.fullyQualifiedDomainName : freshServer!.outputs.fqdn
output databaseName string = postgresSettings.outputs.databaseName
output alertScope string = useExisting ? adoptedServer!.id : freshServer!.outputs.id
