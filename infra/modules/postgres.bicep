param location string
param serverName string
param useExisting bool
param administratorLogin string = 'scentiqadmin'
@secure()
param administratorPassword string = ''
param skuName string = 'Standard_B1ms'

resource newServer 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = if (!useExisting) {
  name: serverName
  location: location
  sku: { name: skuName, tier: 'Burstable' }
  properties: {
    administratorLogin: administratorLogin
    administratorLoginPassword: administratorPassword
    version: '18'
    storage: { storageSizeGB: 32 }
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
    network: { publicNetworkAccess: 'Enabled' }
    highAvailability: { mode: 'Disabled' }
  }
}

resource existingServer 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' existing = if (useExisting) {
  name: serverName
}

output id string = useExisting ? existingServer!.id : newServer!.id
output fqdn string = useExisting ? existingServer!.properties.fullyQualifiedDomainName : newServer!.properties.fullyQualifiedDomainName
