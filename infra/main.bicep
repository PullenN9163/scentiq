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
param webIdentityName string
param migrationIdentityName string
param deploymentIdentityName string
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

module identity 'modules/identity.bicep' = if (!useExistingFoundation) {
  name: 'identity-${environmentName}'
  params: { location: location, identityName: identityName, commonTags: commonTags }
}

module adoptedIdentity 'modules/adopted-identity.bicep' = if (useExistingFoundation) {
  name: 'adopted-identity-${environmentName}'
  params: { identityName: identityName, commonTags: commonTags }
}

module webIdentity 'modules/identity.bicep' = {
  name: 'web-identity-${environmentName}'
  params: { location: location, identityName: webIdentityName, commonTags: commonTags }
}

module migrationIdentity 'modules/identity.bicep' = {
  name: 'migration-identity-${environmentName}'
  params: { location: location, identityName: migrationIdentityName, commonTags: commonTags }
}

module deploymentIdentity 'modules/adopted-identity.bicep' = {
  name: 'deployment-identity-${environmentName}'
  params: { identityName: deploymentIdentityName, commonTags: commonTags }
}

module githubFederation 'modules/federated-identity.bicep' = {
  name: 'github-federation-${environmentName}'
  params: { identityName: deploymentIdentityName }
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

var acrPullRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
var storageBlobDataContributorRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
var keyVaultSecretsUserRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
var contributorRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c')
var roleBasedAccessControlAdministratorRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'f58310d9-a9f6-439a-9e8d-f62e7b41a168')
var acrPushRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8311e382-0749-4cb8-b61a-304f252e45ec')

resource freshAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!useExistingFoundation) {
  name: guid(registryResource.id, identityName, acrPullRoleDefinitionId)
  scope: registryResource
  dependsOn: [registry]
  properties: {
    principalId: identity!.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRoleDefinitionId
  }
}

resource freshBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!useExistingFoundation) {
  name: guid(storageResource.id, identityName, storageBlobDataContributorRoleDefinitionId)
  scope: storageResource
  dependsOn: [storage]
  properties: {
    principalId: identity!.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDataContributorRoleDefinitionId
  }
}

resource freshKeyVaultSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!useExistingFoundation) {
  name: guid(keyVaultResource.id, identityName, keyVaultSecretsUserRoleDefinitionId)
  scope: keyVaultResource
  dependsOn: [keyVault]
  properties: {
    principalId: identity!.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsUserRoleDefinitionId
  }
}

resource adoptedAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (useExistingFoundation) {
  name: guid(registryResource.id, identityPrincipalId, acrPullRoleDefinitionId)
  scope: registryResource
  properties: {
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRoleDefinitionId
  }
}

resource adoptedBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (useExistingFoundation) {
  name: guid(storageResource.id, identityPrincipalId, storageBlobDataContributorRoleDefinitionId)
  scope: storageResource
  properties: {
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDataContributorRoleDefinitionId
  }
}

resource adoptedKeyVaultSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (useExistingFoundation) {
  name: guid(keyVaultResource.id, identityPrincipalId, keyVaultSecretsUserRoleDefinitionId)
  scope: keyVaultResource
  properties: {
    principalId: identityPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsUserRoleDefinitionId
  }
}

resource webAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registryResource.id, webIdentityName, acrPullRoleDefinitionId)
  scope: registryResource
  dependsOn: [registry]
  properties: {
    principalId: webIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRoleDefinitionId
  }
}

resource migrationAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registryResource.id, migrationIdentityName, acrPullRoleDefinitionId)
  scope: registryResource
  dependsOn: [registry]
  properties: {
    principalId: migrationIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRoleDefinitionId
  }
}

resource migrationKeyVaultSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVaultResource.id, migrationIdentityName, keyVaultSecretsUserRoleDefinitionId)
  scope: keyVaultResource
  dependsOn: [keyVault]
  properties: {
    principalId: migrationIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsUserRoleDefinitionId
  }
}

resource deploymentContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, deploymentIdentityName, contributorRoleDefinitionId)
  properties: {
    principalId: deploymentIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: contributorRoleDefinitionId
  }
}

resource deploymentRoleBasedAccessControlAdministrator 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, deploymentIdentityName, roleBasedAccessControlAdministratorRoleDefinitionId)
  properties: {
    principalId: deploymentIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleBasedAccessControlAdministratorRoleDefinitionId
  }
}

resource deploymentAcrPush 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registryResource.id, deploymentIdentityName, acrPushRoleDefinitionId)
  scope: registryResource
  dependsOn: [registry]
  properties: {
    principalId: deploymentIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPushRoleDefinitionId
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
    identityId: useExistingFoundation ? adoptedIdentity!.outputs.id : identity!.outputs.id
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
      { name: 'AZURE_CLIENT_ID', value: useExistingFoundation ? adoptedIdentity!.outputs.clientId : identity!.outputs.clientId }
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
    identityId: webIdentity.outputs.id
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
    identityId: migrationIdentity.outputs.id
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
output apiIdentity object = {
  id: useExistingFoundation ? adoptedIdentity!.outputs.id : identity!.outputs.id
  clientId: useExistingFoundation ? adoptedIdentity!.outputs.clientId : identity!.outputs.clientId
  principalId: useExistingFoundation ? adoptedIdentity!.outputs.principalId : identity!.outputs.principalId
}
output webIdentity object = {
  id: webIdentity.outputs.id
  clientId: webIdentity.outputs.clientId
  principalId: webIdentity.outputs.principalId
}
output migrationIdentity object = {
  id: migrationIdentity.outputs.id
  clientId: migrationIdentity.outputs.clientId
  principalId: migrationIdentity.outputs.principalId
}
output deploymentIdentity object = {
  id: deploymentIdentity.outputs.id
  clientId: deploymentIdentity.outputs.clientId
  principalId: deploymentIdentity.outputs.principalId
}
