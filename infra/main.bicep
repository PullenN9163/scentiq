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
param containerEnvironmentName string
param registryName string
param applicationInsightsName string
param apiAppName string
param webAppName string
param migrationJobName string

param apiImage string = 'mcr.microsoft.com/k8se/quickstart:latest'
param webImage string = 'mcr.microsoft.com/k8se/quickstart:latest'
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

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring-${environmentName}'
  params: {
    location: location
    workspaceName: workspaceName
    applicationInsightsName: applicationInsightsName
    useExistingWorkspace: useExistingFoundation
  }
}

module identity 'modules/identity.bicep' = {
  name: 'identity-${environmentName}'
  params: { location: location, identityName: identityName, useExisting: useExistingFoundation }
}

module registry 'modules/registry.bicep' = {
  name: 'registry-${environmentName}'
  params: { location: location, registryName: registryName, principalId: identity.outputs.principalId }
}

module storage 'modules/storage.bicep' = {
  name: 'storage-${environmentName}'
  params: {
    location: location
    storageName: storageName
    useExisting: useExistingFoundation
    principalId: identity.outputs.principalId
  }
}

module keyVault 'modules/key-vault.bicep' = {
  name: 'key-vault-${environmentName}'
  params: {
    location: location
    vaultName: keyVaultName
    useExisting: useExistingFoundation
    principalId: identity.outputs.principalId
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
  }
}

module containerEnvironment 'modules/container-environment.bicep' = {
  name: 'container-environment-${environmentName}'
  params: {
    location: location
    environmentName: containerEnvironmentName
    useExisting: useExistingFoundation
    workspaceResourceId: monitoring.outputs.workspaceResourceId
  }
}

module api 'modules/container-app.bicep' = if (deployApplications) {
  name: 'api-${environmentName}'
  params: {
    location: location
    name: apiAppName
    environmentId: containerEnvironment.outputs.id
    identityId: identity.outputs.id
    registryServer: registry.outputs.loginServer
    image: apiImage
    targetPort: 8000
    externalIngress: false
    minReplicas: apiMinReplicas
    maxReplicas: apiMaxReplicas
    cpu: '0.5'
    memory: '1Gi'
    applicationInsightsConnectionString: monitoring.outputs.applicationInsightsConnectionString
    databaseSecretUri: databaseSecretUri
    environmentVariables: [
      { name: 'SCENTIQ_ENV', value: environmentName }
      { name: 'CORS_ORIGINS', value: 'https://${webAppName}' }
      { name: 'DEMO_USER_ID', value: '00000000-0000-4000-8000-000000000001' }
      { name: 'AZURE_CLIENT_ID', value: identity.outputs.clientId }
      { name: 'AZURE_STORAGE_ACCOUNT_URL', value: storage.outputs.blobEndpoint }
      { name: 'AZURE_KEY_VAULT_URL', value: keyVault.outputs.uri }
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
    registryServer: registry.outputs.loginServer
    image: webImage
    targetPort: 3000
    externalIngress: true
    minReplicas: webMinReplicas
    maxReplicas: webMaxReplicas
    cpu: '0.5'
    memory: '1Gi'
    applicationInsightsConnectionString: monitoring.outputs.applicationInsightsConnectionString
    environmentVariables: [{ name: 'API_INTERNAL_URL', value: 'https://${api!.outputs.fqdn}' }]
  }
}

module migration 'modules/migration-job.bicep' = if (deployMigration) {
  name: 'migration-${environmentName}'
  params: {
    location: location
    name: migrationJobName
    environmentId: containerEnvironment.outputs.id
    identityId: identity.outputs.id
    registryServer: registry.outputs.loginServer
    image: apiImage
    applicationInsightsConnectionString: monitoring.outputs.applicationInsightsConnectionString
    databaseSecretUri: databaseSecretUri
  }
}

output registryLoginServer string = registry.outputs.loginServer
output apiFqdn string = deployApplications ? api!.outputs.fqdn : ''
output webFqdn string = deployApplications ? web!.outputs.fqdn : ''
output migrationJob string = deployMigration ? migration!.outputs.name : ''
