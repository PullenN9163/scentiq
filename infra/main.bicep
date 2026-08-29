targetScope = 'resourceGroup'

param location string = resourceGroup().location
param postgresLocation string = location
param environmentName string = 'dev'
param useExistingFoundation bool = true
param deployWorkloads bool = false
param deployMigration bool = deployWorkloads
param deployApplications bool = deployWorkloads

param workspaceName string
param storageName string
param keyVaultName string
param postgresServerName string
param identityName string
param identityPrincipalId string
param actionGroupId string
param containerEnvironmentName string
param registryName string
param applicationInsightsName string
param apiAppName string
param webAppName string
param migrationJobName string

param apiImage string = 'scentiqacrdevus.azurecr.io/scentiq-api@sha256:63804207a705c4140ea2be122fc846a05a264beac35be55f29eac23f7d33ff7b'
param webImage string = 'scentiqacrdevus.azurecr.io/scentiq-web@sha256:cd2bcadef061c1b9bf3933623a9de3aefd0b88868f1f6be09808296895ebb3d7'
@secure()
param databaseSecretUri string = ''
@secure()
param postgresAdministratorPassword string = ''
param postgresAdministratorLogin string = 'scentiqadmin'
param postgresSkuName string = 'Standard_B1ms'
param apiMinReplicas int = 1
param apiMaxReplicas int = 2
param webMinReplicas int = 1
param webMaxReplicas int = 2
param commonTags object
@allowed([
  'publicDev'
  'private'
])
param networkMode string = 'publicDev'
param productionApproved bool = false

var workspaceResourceId = resourceId('Microsoft.OperationalInsights/workspaces', workspaceName)

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring-${environmentName}'
  params: {
    location: location
    workspaceName: workspaceName
    applicationInsightsName: applicationInsightsName
    useExistingWorkspace: useExistingFoundation
    commonTags: commonTags
  }
}

module identity 'modules/identity.bicep' = {
  name: 'identity-${environmentName}'
  params: { location: location, identityName: identityName, useExisting: useExistingFoundation, commonTags: commonTags }
}

module registry 'modules/registry.bicep' = {
  name: 'registry-${environmentName}'
  params: { location: location, registryName: registryName, useExisting: useExistingFoundation, commonTags: commonTags }
}

module storage 'modules/storage.bicep' = {
  name: 'storage-${environmentName}'
  params: {
    location: location
    storageName: storageName
    useExisting: useExistingFoundation
    commonTags: commonTags
  }
}

module keyVault 'modules/key-vault.bicep' = {
  name: 'key-vault-${environmentName}'
  params: {
    location: location
    vaultName: keyVaultName
    useExisting: useExistingFoundation
    commonTags: commonTags
  }
}

var registryLoginServer = '${registryName}.azurecr.io'
var storageBlobEndpoint = 'https://${storageName}.blob.${environment().suffixes.storage}/'
var keyVaultUri = 'https://${keyVaultName}.${environment().suffixes.keyvaultDns}/'

resource registryResource 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}

resource storageResource 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageName
}

resource keyVaultResource 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource freshAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!useExistingFoundation) {
  name: guid(registryResource.id, identityName, 'AcrPull')
  scope: registryResource
  dependsOn: [registry]
  properties: {
    principalId: identity.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  }
}

resource freshBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!useExistingFoundation) {
  name: guid(storageResource.id, identityName, 'Storage Blob Data Contributor')
  scope: storageResource
  dependsOn: [storage]
  properties: {
    principalId: identity.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  }
}

resource freshKeyVaultSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!useExistingFoundation) {
  name: guid(keyVaultResource.id, identityName, 'Key Vault Secrets User')
  scope: keyVaultResource
  dependsOn: [keyVault]
  properties: {
    principalId: identity.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b')
  }
}

resource adoptedAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (useExistingFoundation) {
  name: guid(registryResource.id, identityPrincipalId, 'AcrPull')
  scope: registryResource
  properties: {
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  }
}

resource adoptedBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (useExistingFoundation) {
  name: guid(storageResource.id, identityPrincipalId, 'Storage Blob Data Contributor')
  scope: storageResource
  properties: {
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  }
}

resource adoptedKeyVaultSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (useExistingFoundation) {
  name: guid(keyVaultResource.id, identityPrincipalId, 'Key Vault Secrets User')
  scope: keyVaultResource
  properties: {
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
  }
}

module postgres 'modules/postgres.bicep' = {
  name: 'postgres-${environmentName}'
  params: {
    location: postgresLocation
    serverName: postgresServerName
    useExisting: useExistingFoundation
    administratorLogin: postgresAdministratorLogin
    administratorPassword: postgresAdministratorPassword
    skuName: postgresSkuName
    commonTags: commonTags
  }
}

module containerEnvironment 'modules/container-environment.bicep' = {
  name: 'container-environment-${environmentName}'
  dependsOn: [monitoring]
  params: {
    location: location
    environmentName: containerEnvironmentName
    useExisting: useExistingFoundation
    workspaceResourceId: workspaceResourceId
    commonTags: commonTags
  }
}

module api 'modules/container-app.bicep' = if (deployApplications) {
  name: 'api-${environmentName}'
  params: {
    location: location
    name: apiAppName
    environmentId: containerEnvironment.outputs.id
    identityId: identity.outputs.id
    registryServer: registryLoginServer
    image: apiImage
    targetPort: 8000
    externalIngress: false
    minReplicas: apiMinReplicas
    maxReplicas: apiMaxReplicas
    cpu: '0.5'
    memory: '1Gi'
    applicationInsightsConnectionString: monitoring.outputs.applicationInsightsConnectionString
    databaseSecretUri: databaseSecretUri
    commonTags: commonTags
    environmentVariables: [
      { name: 'SCENTIQ_ENV', value: environmentName }
      { name: 'CORS_ORIGINS', value: 'https://${webAppName}' }
      { name: 'DEMO_USER_ID', value: '00000000-0000-4000-8000-000000000001' }
      { name: 'AZURE_CLIENT_ID', value: identity.outputs.clientId }
      { name: 'AZURE_STORAGE_ACCOUNT_URL', value: storageBlobEndpoint }
      { name: 'AZURE_KEY_VAULT_URL', value: keyVaultUri }
    ]
  }
}

module web 'modules/container-app.bicep' = if (deployApplications) {
  name: 'web-${environmentName}'
  params: {
    location: location
    name: webAppName
    environmentId: containerEnvironment.outputs.id
    identityId: identity.outputs.id
    registryServer: registryLoginServer
    image: webImage
    targetPort: 3000
    externalIngress: true
    minReplicas: webMinReplicas
    maxReplicas: webMaxReplicas
    cpu: '0.5'
    memory: '1Gi'
    applicationInsightsConnectionString: monitoring.outputs.applicationInsightsConnectionString
    environmentVariables: [{ name: 'API_INTERNAL_URL', value: 'https://${api!.outputs.fqdn}' }]
    commonTags: commonTags
  }
}

module migration 'modules/migration-job.bicep' = if (deployMigration) {
  name: 'migration-${environmentName}'
  params: {
    location: location
    name: migrationJobName
    environmentId: containerEnvironment.outputs.id
    identityId: identity.outputs.id
    registryServer: registryLoginServer
    image: apiImage
    applicationInsightsConnectionString: monitoring.outputs.applicationInsightsConnectionString
    databaseSecretUri: databaseSecretUri
    commonTags: commonTags
  }
}

output registryLoginServer string = registryLoginServer
output governanceActionGroupId string = actionGroupId
output apiFqdn string = deployApplications ? api!.outputs.fqdn : ''
output webFqdn string = deployApplications ? web!.outputs.fqdn : ''
output migrationJob string = deployMigration ? migration!.outputs.name : ''
output selectedNetworkMode string = networkMode
output productionDeploymentApproved bool = productionApproved
