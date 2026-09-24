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
param commonTags object
@secure()
param applicationInsightsConnectionString string
@secure()
param databaseSecretUri string = ''

@description('''
Additional Key Vault-backed secrets. Each entry is
{ name: <container app secret name>, envVar: <environment variable>, keyVaultUrl: <secret URI> }.
An entry with an empty keyVaultUrl is skipped, so a deployment can omit a
secret without changing the template.
''')
param keyVaultSecrets array = []

var suppliedSecrets = filter(keyVaultSecrets, secret => !empty(secret.keyVaultUrl))

var secrets = concat(
  [{ name: 'application-insights', value: applicationInsightsConnectionString }],
  empty(databaseSecretUri) ? [] : [{ name: 'database-url', keyVaultUrl: databaseSecretUri, identity: identityId }],
  map(suppliedSecrets, secret => {
    name: secret.name
    keyVaultUrl: secret.keyVaultUrl
    identity: identityId
  })
)

resource app 'Microsoft.App/containerApps@2025-01-01' = {
  name: name
  location: location
  tags: commonTags
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
          empty(databaseSecretUri) ? [] : [{ name: 'DATABASE_URL', secretRef: 'database-url' }],
          map(suppliedSecrets, secret => {
            name: secret.envVar
            secretRef: secret.name
          })
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
