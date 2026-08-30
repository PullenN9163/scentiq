using '../subscription.bicep'

param resourceGroupName = 'scentiq-rg-dev-eus'
param location = 'eastus'
param postgresLocation = 'northcentralus'
param environmentName = 'dev'
param owner = 'platform-owner'
param costCenter = 'scentiq-development'
param dataClassification = 'nonproduction'
param alertEmails = '[]'
param budgetAmount = 50
param deploymentMode = 'dev'
param networkMode = 'publicDev'
param productionApproved = false
param useExistingFoundation = true
// Shared Key disablement and delete locks are enabled after identity and recovery rehearsals.
param enableStorageSharedKeyAccess = true
param enableFoundationLocks = false
// PostgreSQL protection follows the same staged path: enable it only after its first successful in-place deployment and recovery rehearsal.
param enablePostgresLock = false
param workspaceName = 'scentiq-law-dev-us'
param workspaceExistingTags = {
  Project: 'scentiq'
  'cost-center': 'personal-project'
  environment: 'development'
  'managed-by': 'manual'
  owner: 'nas'
}
param storageName = 'scentiqstrgdevus'
param keyVaultName = 'scentiq-kv-dev-eus'
param postgresServerName = 'scentiq-pg-dev-eus'
param postgresTenantId = '8bf88c8e-62b5-49b1-a18a-296adc261f74'
param postgresAzureServicesFirewallRuleName = 'AllowAllAzureServicesAndResourcesWithinAzureIps_2026-8-6_22-2-8'
param postgresExistingTags = {
  Project: 'scentiq'
  'cost-center': 'personal-project'
  environment: 'development'
  'managed-by': 'manual'
  owner: 'nas'
}
param identityName = 'scentiq-api-id-dev-eus'
param identityPrincipalId = 'bf64241d-7973-47a1-9a2c-5f96b9b6ea86'
param webIdentityName = 'scentiq-web-id-dev-eus'
param migrationIdentityName = 'scentiq-migrate-id-dev-eus'
param deploymentIdentityName = 'scentiq-github-deploy-dev-eus'
param deploymentIdentityPrincipalId = '5f61ffc1-a14e-4b49-9b17-c09aa190b9e8'
param apiBlobRoleAssignmentName = '1158c045-8a90-4051-8e5a-1cfde68585b1'
param apiKeyVaultRoleAssignmentName = '672eced6-659f-4a25-89c7-af674fc9f265'
param deploymentContributorRoleAssignmentName = '4dbd1152-0ec7-48bc-8dae-ce62f6ba579b'
param deploymentRbacAdministratorRoleAssignmentName = 'dc65aebd-990d-42b4-add7-9665ce128edc'
param deploymentAcrPushRoleAssignmentName = 'd1ddf565-2368-4057-bbb8-7febfda4b05c'
param containerEnvironmentName = 'scentiq-cae-dev-eus'
param registryName = 'scentiqacrdevus'
param applicationInsightsName = 'scentiq-appi-dev-eus'
param apiAppName = 'scentiq-api-dev-eus'
param webAppName = 'scentiq-web-dev-eus'
param migrationJobName = 'scentiq-migrate-dev-eus'
param apiImage = 'scentiqacrdevus.azurecr.io/scentiq-api@sha256:63804207a705c4140ea2be122fc846a05a264beac35be55f29eac23f7d33ff7b'
param webImage = 'scentiqacrdevus.azurecr.io/scentiq-web@sha256:cd2bcadef061c1b9bf3933623a9de3aefd0b88868f1f6be09808296895ebb3d7'
