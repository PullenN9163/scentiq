param location string
param identityName string
param useExisting bool
param commonTags object

resource newIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = if (!useExisting) {
  name: identityName
  location: location
  tags: commonTags
}

resource existingIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: identityName
}

resource existingIdentityTags 'Microsoft.Resources/tags@2025-04-01' = if (useExisting) {
  name: 'default'
  scope: existingIdentity
  properties: {
    tags: union(existingIdentity.tags, commonTags)
  }
}

output id string = useExisting ? existingIdentity!.id : newIdentity!.id
output principalId string = useExisting ? existingIdentity!.properties.principalId : newIdentity!.properties.principalId
output clientId string = useExisting ? existingIdentity!.properties.clientId : newIdentity!.properties.clientId
