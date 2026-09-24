param identityName string

resource deploymentIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: identityName
}

// Two credentials are declared because GitHub emits the subject claim in two
// formats. The name-based form is the original; the immutable form embeds the
// numeric owner and repository IDs so that renaming either cannot silently
// transfer trust to a different repository. GitHub now presents the immutable
// form, and a deployment fails with AADSTS700213 if only the other is present.
// Both describe the same repository and environment, so neither widens access.
resource githubDevelopment 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: deploymentIdentity
  name: 'github-scentiq-development'
  properties: {
    audiences: [
      'api://AzureADTokenExchange'
    ]
    issuer: 'https://token.actions.githubusercontent.com'
    subject: 'repo:PullenN9163/scentiq:environment:development'
  }
}

resource githubDevelopmentImmutable 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: deploymentIdentity
  name: 'github-scentiq-development-immutable'
  // Credentials on one identity must be created serially; Azure rejects
  // concurrent writes to the same parent.
  dependsOn: [
    githubDevelopment
  ]
  properties: {
    audiences: [
      'api://AzureADTokenExchange'
    ]
    issuer: 'https://token.actions.githubusercontent.com'
    subject: 'repo:PullenN9163@194549953/scentiq@1327919888:environment:development'
  }
}
