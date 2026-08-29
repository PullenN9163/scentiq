param location string
param storageName string
param useExisting bool
param commonTags object

resource newStorage 'Microsoft.Storage/storageAccounts@2023-05-01' = if (!useExisting) {
  name: storageName
  location: location
  tags: commonTags
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Enabled'
  }
}

resource existingStorage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageName
}

resource existingStorageTags 'Microsoft.Resources/tags@2025-04-01' = if (useExisting) {
  name: 'default'
  scope: existingStorage
  properties: {
    tags: union(existingStorage.tags, commonTags)
  }
}

output id string = useExisting ? existingStorage!.id : newStorage!.id
output blobEndpoint string = useExisting ? existingStorage!.properties.primaryEndpoints.blob : newStorage!.properties.primaryEndpoints.blob
