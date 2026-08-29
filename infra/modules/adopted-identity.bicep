param identityName string
param commonTags object

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: identityName
}

resource identityTags 'Microsoft.Resources/tags@2025-04-01' = {
  name: 'default'
  scope: identity
  properties: {
    tags: union(identity.tags, commonTags)
  }
}

output id string = identity.id
output principalId string = identity.properties.principalId
output clientId string = identity.properties.clientId
