param location string
param name string
param environmentId string
param identityId string
param registryServer string
param image string
param targetPort int
param externalIngress bool
param minReplicas int
param maxReplicas int
param cpu string
param memory string
param environmentVariables array
@secure()
param applicationInsightsConnectionString string
@secure()
param databaseSecretUri string = ''

var secrets = concat(
  [{ name: 'application-insights', value: applicationInsightsConnectionString }],
  empty(databaseSecretUri) ? [] : [{ name: 'database-url', keyVaultUrl: databaseSecretUri, identity: identityId }]
)

resource app 'Microsoft.App/containerApps@2025-01-01' = {
  name: name
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identityId}': {} }
  }
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: externalIngress
        targetPort: targetPort
        transport: 'auto'
        allowInsecure: false
      }
      registries: [{ server: registryServer, identity: identityId }]
      secrets: secrets
    }
    template: {
      containers: [{
        name: name
        image: image
        env: concat(
          environmentVariables,
          [{ name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'application-insights' }],
          empty(databaseSecretUri) ? [] : [{ name: 'DATABASE_URL', secretRef: 'database-url' }]
        )
        resources: { cpu: json(cpu), memory: memory }
        probes: [{
          type: 'Liveness'
          httpGet: { path: targetPort == 8000 ? '/health/live' : '/', port: targetPort, scheme: 'HTTP' }
          initialDelaySeconds: 10
          periodSeconds: 15
        }]
      }]
      scale: { minReplicas: minReplicas, maxReplicas: maxReplicas }
    }
  }
}

output fqdn string = app.properties.configuration.ingress.fqdn
output name string = app.name
