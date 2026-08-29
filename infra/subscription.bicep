targetScope = 'subscription'

param resourceGroupName string
param location string
param postgresLocation string = location
param environmentName string = 'dev'
param owner string
param costCenter string
param dataClassification string
@secure()
param alertEmails string
param budgetAmount int = 50
@allowed([
  'dev'
  'test'
  'prod-reference'
])
param deploymentMode string = 'dev'
@allowed([
  'publicDev'
  'private'
])
param networkMode string = 'publicDev'
param productionApproved bool = false

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
param containerEnvironmentName string
param registryName string
param applicationInsightsName string
param apiAppName string
param webAppName string
param migrationJobName string

param apiImage string
param webImage string
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

assert productionGate = environmentName != 'prod' || productionApproved

var commonTags = {
  application: 'scentiq'
  environment: environmentName
  owner: owner
  'cost-center': costCenter
  'managed-by': 'bicep'
  'data-classification': dataClassification
}

resource resourceGroup 'Microsoft.Resources/resourceGroups@2024-03-01' existing = {
  name: resourceGroupName
}

module resourceGroupTags 'modules/resource-group-tags.bicep' = {
  name: 'resource-group-tags-${environmentName}'
  scope: resourceGroup
  params: {
    commonTags: commonTags
  }
}

module governance 'modules/governance.bicep' = {
  name: 'governance-${environmentName}'
  scope: resourceGroup
  params: {
    environmentName: environmentName
    alertEmails: json(alertEmails)
    budgetAmount: budgetAmount
    commonTags: commonTags
  }
}

module platform 'main.bicep' = {
  name: 'platform-${environmentName}'
  scope: resourceGroup
  params: {
    location: location
    postgresLocation: postgresLocation
    environmentName: environmentName
    useExistingFoundation: useExistingFoundation
    deployWorkloads: deployWorkloads
    deployMigration: deployMigration
    deployApplications: deployApplications
    workspaceName: workspaceName
    storageName: storageName
    keyVaultName: keyVaultName
    postgresServerName: postgresServerName
    identityName: identityName
    identityPrincipalId: identityPrincipalId
    actionGroupId: '${subscription().id}/resourceGroups/${resourceGroupName}/providers/Microsoft.Insights/actionGroups/scentiq-ag-${environmentName}-eus'
    containerEnvironmentName: containerEnvironmentName
    registryName: registryName
    applicationInsightsName: applicationInsightsName
    apiAppName: apiAppName
    webAppName: webAppName
    migrationJobName: migrationJobName
    apiImage: apiImage
    webImage: webImage
    databaseSecretUri: databaseSecretUri
    postgresAdministratorPassword: postgresAdministratorPassword
    postgresAdministratorLogin: postgresAdministratorLogin
    postgresSkuName: postgresSkuName
    apiMinReplicas: apiMinReplicas
    apiMaxReplicas: apiMaxReplicas
    webMinReplicas: webMinReplicas
    webMaxReplicas: webMaxReplicas
    commonTags: commonTags
    networkMode: networkMode
    productionApproved: productionApproved
  }
}

output resourceGroupId string = resourceGroup.id
output commonTags object = commonTags
output actionGroupId string = governance.outputs.actionGroupId
output budgetName string = governance.outputs.budgetName
output selectedDeploymentMode string = deploymentMode
