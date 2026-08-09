param location string
param name string
param environmentId string
param identityId string
param registryServer string
param image string
@secure()
param applicationInsightsConnectionString string
@secure()
param databaseSecretUri string

resource job 'Microsoft.App/jobs@2025-01-01' = {
  name: name
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identityId}': {} }
  }
  properties: {
    environmentId: environmentId
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 1800
      replicaRetryLimit: 1
      manualTriggerConfig: { parallelism: 1, replicaCompletionCount: 1 }
      registries: [{ server: registryServer, identity: identityId }]
      secrets: [
        { name: 'database-url', keyVaultUrl: databaseSecretUri, identity: identityId }
        { name: 'application-insights', value: applicationInsightsConnectionString }
      ]
    }
    template: {
      containers: [{
        name: 'migration'
        image: image
        command: ['.venv/bin/alembic']
        args: ['upgrade', 'head']
        env: [
          { name: 'SCENTIQ_ENV', value: 'development' }
          { name: 'CORS_ORIGINS', value: 'https://localhost.invalid' }
          { name: 'DATABASE_URL', secretRef: 'database-url' }
          { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'application-insights' }
        ]
        resources: { cpu: json('0.5'), memory: '1Gi' }
      }]
    }
  }
}

output name string = job.name
