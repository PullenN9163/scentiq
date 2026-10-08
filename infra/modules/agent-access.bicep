// Integrates an operator-selected existing Azure OpenAI/Foundry account.
// Model deployment is a quota/region prerequisite; this module never creates one.
param accountName string
param projectName string = ''
param apiPrincipalId string

resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: accountName
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' existing = if (!empty(projectName)) {
  parent: account
  name: projectName
}

// Cognitive Services OpenAI User: inference permissions without key management.
var inferenceRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
resource inferenceRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, apiPrincipalId, inferenceRoleId)
  scope: account
  properties: {
    roleDefinitionId: inferenceRoleId
    principalId: apiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output accountId string = account.id
output projectId string = empty(projectName) ? '' : project!.id
output roleAssignmentId string = inferenceRole.id
