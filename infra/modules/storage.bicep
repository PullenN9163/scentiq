param location string
param storageName string
param commonTags object
param workspaceResourceId string
param enableStorageSharedKeyAccess bool = false
param enableFoundationLocks bool = true

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowCrossTenantReplication: false
    allowSharedKeyAccess: enableStorageSharedKeyAccess
    defaultToOAuthAuthentication: true
    minimumTlsVersion: 'TLS1_2'
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Allow'
      ipRules: []
      virtualNetworkRules: []
    }
    publicNetworkAccess: 'Enabled'
    supportsHttpsTrafficOnly: true
  }
}

resource storageTags 'Microsoft.Resources/tags@2025-04-01' = {
  name: 'default'
  scope: storage
  properties: {
    tags: union(storage.tags, commonTags)
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    changeFeed: {
      enabled: true
    }
    containerDeleteRetentionPolicy: {
      days: 14
      enabled: true
    }
    cors: {
      corsRules: []
    }
    deleteRetentionPolicy: {
      allowPermanentDelete: false
      days: 14
      enabled: true
    }
    isVersioningEnabled: true
  }
}

resource uploadsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'uploads'
  properties: {
    defaultEncryptionScope: '$account-encryption-key'
    denyEncryptionScopeOverride: false
    publicAccess: 'None'
  }
}

resource exportsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'exports'
  properties: {
    defaultEncryptionScope: '$account-encryption-key'
    denyEncryptionScopeOverride: false
    publicAccess: 'None'
  }
}

resource systemContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'system'
  properties: {
    defaultEncryptionScope: '$account-encryption-key'
    denyEncryptionScopeOverride: false
    publicAccess: 'None'
  }
}

resource managementPolicy 'Microsoft.Storage/storageAccounts/managementPolicies@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    policy: {
      rules: [
        {
          name: 'delete-temporary-exports-after-seven-days'
          enabled: true
          type: 'Lifecycle'
          definition: {
            actions: {
              baseBlob: {
                delete: {
                  daysAfterModificationGreaterThan: 7
                }
              }
            }
            filters: {
              blobTypes: [
                'blockBlob'
              ]
              prefixMatch: [
                'exports/temporary/'
              ]
            }
          }
        }
      ]
    }
  }
}

resource diagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  scope: storage
  name: 'scentiq-storage-audit'
  properties: {
    workspaceId: workspaceResourceId
    logs: [
      {
        category: 'StorageRead'
        enabled: true
      }
      {
        category: 'StorageWrite'
        enabled: true
      }
      {
        category: 'StorageDelete'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'Transaction'
        enabled: true
      }
    ]
  }
}

resource storageLock 'Microsoft.Authorization/locks@2020-05-01' = if (enableFoundationLocks) {
  scope: storage
  name: 'scentiq-storage-protection'
  properties: {
    level: 'CanNotDelete'
    notes: 'Protects ScentIQ storage data. Follow the Azure recovery runbook before removing this lock.'
  }
}

output id string = storage.id
output blobEndpoint string = 'https://${storageName}.blob.${environment().suffixes.storage}/'
output containerIds object = {
  uploads: uploadsContainer.id
  exports: exportsContainer.id
  system: systemContainer.id
}
