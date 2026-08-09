param location string
param identityName string
param useExisting bool

resource newIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = if (!useExisting) {
  name: identityName
  location: location
}

resource existingIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = if (useExisting) {
  name: identityName
}

output id string = useExisting ? existingIdentity!.id : newIdentity!.id
output principalId string = useExisting ? existingIdentity!.properties.principalId : newIdentity!.properties.principalId
output clientId string = useExisting ? existingIdentity!.properties.clientId : newIdentity!.properties.clientId
