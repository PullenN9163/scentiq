param location string
param vaultName string
param commonTags object
param workspaceResourceId string
param enableFoundationLocks bool = true

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: vaultName
  location: location
  properties: {
    accessPolicies: []
    tenantId: tenant().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enablePurgeProtection: true
    enableRbacAuthorization: true
    enableSoftDelete: true
    enabledForDeployment: false
    enabledForDiskEncryption: false
    enabledForTemplateDeployment: false
    networkAcls: {
      bypass: 'None'
      defaultAction: 'Allow'
      ipRules: []
      virtualNetworkRules: []
    }
    publicNetworkAccess: 'Enabled'
    softDeleteRetentionInDays: 7
  }
}

resource vaultTags 'Microsoft.Resources/tags@2025-04-01' = {
  name: 'default'
  scope: vault
  properties: {
    tags: union(vault.tags, commonTags)
  }
}

resource diagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  scope: vault
  name: 'scentiq-key-vault-audit'
  properties: {
    workspaceId: workspaceResourceId
    logs: [
      {
        category: 'AuditEvent'
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

resource keyVaultLock 'Microsoft.Authorization/locks@2020-05-01' = if (enableFoundationLocks) {
  scope: vault
  name: 'scentiq-key-vault-protection'
  properties: {
    level: 'CanNotDelete'
    notes: 'Protects ScentIQ Key Vault. Follow the Azure recovery runbook before removing this lock.'
  }
}

output id string = vault.id
output uri string = vault.properties.vaultUri
