param location string
param vaultName string
param useExisting bool
param commonTags object
param workspaceResourceId string
param enableFoundationLocks bool = true

resource newVault 'Microsoft.KeyVault/vaults@2023-07-01' = if (!useExisting) {
  name: vaultName
  location: location
  tags: commonTags
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

resource existingVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: vaultName
}

resource vaultTags 'Microsoft.Resources/tags@2025-04-01' = if (useExisting) {
  name: 'default'
  scope: existingVault
  properties: {
    tags: union(existingVault.tags, commonTags)
  }
}

resource diagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  scope: existingVault
  name: 'scentiq-key-vault-audit'
  dependsOn: [
    newVault
  ]
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
  scope: existingVault
  name: 'scentiq-key-vault-protection'
  dependsOn: [
    newVault
  ]
  properties: {
    level: 'CanNotDelete'
    notes: 'Protects ScentIQ Key Vault. Follow the Azure recovery runbook before removing this lock.'
  }
}

output id string = existingVault.id
output uri string = useExisting ? existingVault.properties.vaultUri : newVault!.properties.vaultUri
