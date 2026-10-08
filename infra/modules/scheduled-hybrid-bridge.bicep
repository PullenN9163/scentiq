param location string
param name string
param environmentId string
param identityId string
param identityClientId string
param registryServer string
param image string
param environmentName string
param catalogVersion string
param storageAccountUrl string
@secure()
param applicationInsightsConnectionString string
@secure()
param databaseSecretUri string
param commonTags object

resource job 'Microsoft.App/jobs@2025-01-01' = {
  name: name
  location: location
  tags: commonTags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identityId}': {} }
  }
  properties: {
    environmentId: environmentId
    configuration: {
      triggerType: 'Schedule'
      replicaTimeout: 300
      replicaRetryLimit: 1
      scheduleTriggerConfig: {
        cronExpression: '* * * * *'
        parallelism: 1
        replicaCompletionCount: 1
      }
      registries: [{ server: registryServer, identity: identityId }]
      secrets: [
        { name: 'database-url', keyVaultUrl: databaseSecretUri, identity: identityId }
        { name: 'application-insights', value: applicationInsightsConnectionString }
      ]
    }
    template: {
      containers: [{
        name: 'hybrid-bridge'
        image: image
        command: ['.venv/bin/python']
        args: ['-m', 'scentiq_api.hybrid', 'bridge', '--catalog-version', catalogVersion]
        env: [
          { name: 'SCENTIQ_ENV', value: environmentName }
          { name: 'AZURE_CLIENT_ID', value: identityClientId }
          { name: 'CORS_ORIGINS', value: 'https://localhost.invalid' }
          { name: 'AZURE_STORAGE_ACCOUNT_URL', value: storageAccountUrl }
          { name: 'DATABASE_URL', secretRef: 'database-url' }
          { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'application-insights' }
        ]
        resources: { cpu: json('0.25'), memory: '0.5Gi' }
      }]
    }
  }
}

output name string = job.name
