param location string
param storageName string
param useExisting bool
param principalId string

resource newStorage 'Microsoft.Storage/storageAccounts@2023-05-01' = if (!useExisting) {
  name: storageName
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Enabled'
  }
}

resource existingStorage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = if (useExisting) {
  name: storageName
}

resource blobRoleNew 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!useExisting) {
  name: guid(newStorage.id, principalId, 'Storage Blob Data Contributor')
  scope: newStorage
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  }
}

output id string = useExisting ? existingStorage!.id : newStorage!.id
output blobEndpoint string = useExisting ? existingStorage!.properties.primaryEndpoints.blob : newStorage!.properties.primaryEndpoints.blob
