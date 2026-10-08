param serverName string
param commonTags object

resource server 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' existing = {
  name: serverName
}

resource tags 'Microsoft.Resources/tags@2025-04-01' = {
  name: 'default'
  scope: server
  properties: {
    tags: union(server.tags, commonTags)
  }
}
