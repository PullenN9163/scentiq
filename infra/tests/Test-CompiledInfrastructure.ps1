param(
    [Parameter(Mandatory)] [string] $TemplatePath,
    [Parameter(Mandatory)] [ValidateSet('dev', 'test', 'prod-reference')] [string] $Mode
)

$template = Get-Content -Raw -LiteralPath $TemplatePath | ConvertFrom-Json -Depth 100
$failures = [System.Collections.Generic.List[string]]::new()
$roleDefinitionExpressions = @{}

function Assert-True([bool] $Condition, [string] $Message) {
    if (-not $Condition) { $script:failures.Add($Message) }
}

function Get-ArmResources([object] $Resources) {
    $resourceItems = if ($Resources -is [System.Array]) {
        $Resources
    }
    elseif ($null -eq $Resources) {
        @()
    }
    else {
        @($Resources.PSObject.Properties | ForEach-Object { $_.Value })
    }

    foreach ($resource in $resourceItems) {
        $resource
        if ($resource.properties.template.variables) {
            foreach ($variable in $resource.properties.template.variables.PSObject.Properties) {
                $script:roleDefinitionExpressions[$variable.Name] = $variable.Value
            }
        }
        if ($resource.properties.template.resources) {
            Get-ArmResources $resource.properties.template.resources
        }
    }
}

function Test-RoleDefinition([object] $Assignment, [string] $RoleDefinitionId) {
    $value = [string] $Assignment.properties.roleDefinitionId
    if ($value -match [regex]::Escape($RoleDefinitionId)) {
        return $true
    }

    if ($value -match "variables\('([^']+)'\)") {
        return ([string] $script:roleDefinitionExpressions[$Matches[1]]) -match [regex]::Escape($RoleDefinitionId)
    }

    return $false
}

$resources = @(Get-ArmResources $template.resources)
Assert-True ($resources.Count -gt 0) 'compiled template contains no resources'
Assert-True (-not ($template | ConvertTo-Json -Depth 100 | Select-String -Quiet 'latest')) 'mutable latest image tag is forbidden'
Assert-True (-not ($template | ConvertTo-Json -Depth 100 | Select-String -Quiet '0\.0\.0\.0/0')) 'unrestricted CIDR is forbidden'

if ($Mode -eq 'dev') {
    $createdWorkloadIdentities = @($resources | Where-Object { $_.type -eq 'Microsoft.ManagedIdentity/userAssignedIdentities' -and -not $_.existing })
    $adoptedWorkloadIdentities = @($resources | Where-Object { $_.type -eq 'Microsoft.ManagedIdentity/userAssignedIdentities' -and $_.existing })
    Assert-True ($createdWorkloadIdentities.Count -eq 3 -and $adoptedWorkloadIdentities.Count -eq 3) 'development must declare dedicated API, web, migration, and GitHub deployment identities without duplicate create/adopt declarations'

    $federatedCredentials = @($resources | Where-Object { $_.type -eq 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials' })
    $githubFederatedCredential = $federatedCredentials | Select-Object -First 1
    Assert-True ($federatedCredentials.Count -eq 1) 'development must declare exactly one GitHub federated credential'
    Assert-True ($null -ne $githubFederatedCredential -and $githubFederatedCredential.properties.issuer -eq 'https://token.actions.githubusercontent.com') 'GitHub federated credential must use the GitHub Actions issuer'
    Assert-True ($null -ne $githubFederatedCredential -and $githubFederatedCredential.properties.subject -eq 'repo:PullenN9163/scentiq:environment:development') 'GitHub federated credential must be restricted to the development environment'
    Assert-True ($null -ne $githubFederatedCredential -and $githubFederatedCredential.properties.audiences.Count -eq 1 -and $githubFederatedCredential.properties.audiences[0] -eq 'api://AzureADTokenExchange') 'GitHub federated credential must use the Azure AD token exchange audience'

    $platformIdentityOutputs = @('apiIdentity', 'webIdentity', 'migrationIdentity', 'deploymentIdentity')
    $platformDeploymentForIdentityContracts = @($resources | Where-Object { $_.type -eq 'Microsoft.Resources/deployments' -and $_.name -match 'platform-' }) | Select-Object -First 1
    foreach ($identityOutput in $platformIdentityOutputs) {
        $contract = $platformDeploymentForIdentityContracts.properties.template.outputs.$identityOutput
        Assert-True ($null -ne $contract -and $contract.type -eq 'object') "platform must expose the $identityOutput identity contract"
        Assert-True ($null -ne $contract -and @($contract.value.PSObject.Properties.Name | Where-Object { $_ -in @('id', 'clientId', 'principalId') }).Count -eq 3) "the $identityOutput identity contract must contain id, clientId, and principalId"
    }

    $roleAssignments = @($resources | Where-Object { $_.type -eq 'Microsoft.Authorization/roleAssignments' })
    $roleDefinitions = @{
        AcrPull = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
        BlobContributor = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
        KeyVaultSecretsUser = '4633458b-17de-408a-b874-0445c86b69e6'
        Contributor = 'b24988ac-6180-42a0-ab88-20f7382dd24c'
        RbacAdministrator = 'f58310d9-a9f6-439a-9e8d-f62e7b41a168'
        AcrPush = '8311e382-0749-4cb8-b61a-304f252e45ec'
    }
    $acrPullAssignments = @($roleAssignments | Where-Object { Test-RoleDefinition $_ $roleDefinitions.AcrPull })
    $blobAssignments = @($roleAssignments | Where-Object { Test-RoleDefinition $_ $roleDefinitions.BlobContributor })
    $keyVaultAssignments = @($roleAssignments | Where-Object { Test-RoleDefinition $_ $roleDefinitions.KeyVaultSecretsUser })
    Assert-True ($acrPullAssignments.Count -eq 4 -and @($acrPullAssignments | Where-Object { $_.scope -notmatch 'Microsoft.ContainerRegistry/registries' }).Count -eq 0) 'API, web, migration, and deployment identities must receive AcrPull or AcrPush only at the registry scope'
    Assert-True ($blobAssignments.Count -eq 2 -and @($blobAssignments | Where-Object { $_.scope -notmatch 'Microsoft.Storage/storageAccounts' }).Count -eq 0) 'API identity must receive Storage Blob Data Contributor only at the storage account scope'
    Assert-True ($keyVaultAssignments.Count -eq 3 -and @($keyVaultAssignments | Where-Object { $_.scope -notmatch 'Microsoft.KeyVault/vaults' }).Count -eq 0) 'API and migration identities must receive Key Vault Secrets User only at the vault scope'
    Assert-True ((@($roleAssignments | Where-Object { Test-RoleDefinition $_ $roleDefinitions.Contributor }).Count) -eq 1) 'deployment identity must retain Contributor'
    Assert-True ((@($roleAssignments | Where-Object { Test-RoleDefinition $_ $roleDefinitions.RbacAdministrator }).Count) -eq 1) 'deployment identity must retain Role Based Access Control Administrator'
    Assert-True ((@($roleAssignments | Where-Object { (Test-RoleDefinition $_ $roleDefinitions.AcrPush) -and $_.scope -match 'Microsoft.ContainerRegistry/registries' }).Count) -eq 1) 'deployment identity must retain AcrPush at the registry scope'
    Assert-True ((@($roleAssignments | Where-Object { $_.properties.principalType -ne 'ServicePrincipal' }).Count) -eq 0) 'all identity role assignments must declare ServicePrincipal principals'
    Assert-True ((@($roleAssignments | Where-Object { $_.condition -match "not\(parameters\('useExistingFoundation'\)\)" -and $_.name -notmatch 'guid\(' }).Count) -eq 0) 'fresh identity role assignment names must be deterministic GUID expressions'

    $apiAssignments = @($roleAssignments | Where-Object { $_.condition -match "parameters\('useExistingFoundation'\)" })
    $webAssignments = @($roleAssignments | Where-Object { $_.properties.principalId -match "reference\('webIdentity'\)\.outputs\.principalId\.value" })
    $migrationAssignments = @($roleAssignments | Where-Object { $_.properties.principalId -match "reference\('migrationIdentity'\)\.outputs\.principalId\.value" })
    $deploymentAssignments = @($roleAssignments | Where-Object { $_.properties.principalId -eq "[parameters('deploymentIdentityPrincipalId')]" })
    $adoptedAssignmentNames = @(
        'apiBlobRoleAssignmentName',
        'apiKeyVaultRoleAssignmentName',
        'deploymentContributorRoleAssignmentName',
        'deploymentRbacAdministratorRoleAssignmentName',
        'deploymentAcrPushRoleAssignmentName'
    )
    foreach ($assignmentNameParameter in $adoptedAssignmentNames) {
        Assert-True ((@($roleAssignments | Where-Object { $_.name -eq "[parameters('$assignmentNameParameter')]" }).Count) -eq 1) "adopted role assignment must use the explicit $assignmentNameParameter contract"
    }
    Assert-True ($apiAssignments.Count -eq 6 -and @($apiAssignments | Where-Object { Test-RoleDefinition $_ $roleDefinitions.AcrPull }).Count -eq 2 -and @($apiAssignments | Where-Object { Test-RoleDefinition $_ $roleDefinitions.BlobContributor }).Count -eq 2 -and @($apiAssignments | Where-Object { Test-RoleDefinition $_ $roleDefinitions.KeyVaultSecretsUser }).Count -eq 2) 'API identity must have exactly AcrPull, Storage Blob Data Contributor, and Key Vault Secrets User across fresh and adopted branches'
    Assert-True ($webAssignments.Count -eq 1 -and (Test-RoleDefinition $webAssignments[0] $roleDefinitions.AcrPull)) 'web identity must have only AcrPull'
    Assert-True ($migrationAssignments.Count -eq 2 -and @($migrationAssignments | Where-Object { Test-RoleDefinition $_ $roleDefinitions.AcrPull }).Count -eq 1 -and @($migrationAssignments | Where-Object { Test-RoleDefinition $_ $roleDefinitions.KeyVaultSecretsUser }).Count -eq 1) 'migration identity must have exactly AcrPull and Key Vault Secrets User'
    Assert-True ($deploymentAssignments.Count -eq 3 -and @($deploymentAssignments | Where-Object { Test-RoleDefinition $_ $roleDefinitions.Contributor }).Count -eq 1 -and @($deploymentAssignments | Where-Object { Test-RoleDefinition $_ $roleDefinitions.RbacAdministrator }).Count -eq 1 -and @($deploymentAssignments | Where-Object { Test-RoleDefinition $_ $roleDefinitions.AcrPush }).Count -eq 1) 'deployment identity must retain exactly Contributor, Role Based Access Control Administrator, and AcrPush'

    $requiredTypes = @(
        'Microsoft.Insights/actionGroups',
        'Microsoft.Consumption/budgets'
    )
    foreach ($type in $requiredTypes) {
        Assert-True (($resources.type -contains $type)) "missing required resource type $type"
    }

    $budget = @($resources | Where-Object { $_.type -eq 'Microsoft.Consumption/budgets' }) | Select-Object -First 1
    Assert-True ($null -ne $budget -and ([datetime] $budget.properties.timePeriod.startDate).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') -eq '2026-08-01T00:00:00Z') 'budget must preserve the existing adoption start date'
    Assert-True ($null -ne $budget -and ([datetime] $budget.properties.timePeriod.endDate).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') -eq '2036-08-01T00:00:00Z') 'budget must preserve the existing adoption end date'
    $expectedBudgetNotifications = @{
        actual_50 = @{ threshold = 50; thresholdType = 'Actual' }
        actual_80 = @{ threshold = 80; thresholdType = 'Actual' }
        actual_100 = @{ threshold = 100; thresholdType = 'Actual' }
        actual_120 = @{ threshold = 120; thresholdType = 'Actual' }
        forecast_80 = @{ threshold = 80; thresholdType = 'Forecasted' }
    }
    foreach ($notificationName in $expectedBudgetNotifications.Keys) {
        $notification = $budget.properties.notifications.$notificationName
        Assert-True ($null -ne $notification) "budget is missing required notification $notificationName"
        Assert-True ($null -ne $notification -and $notification.threshold -eq $expectedBudgetNotifications[$notificationName].threshold) "budget notification $notificationName has an incorrect threshold"
        Assert-True ($null -ne $notification -and $notification.thresholdType -eq $expectedBudgetNotifications[$notificationName].thresholdType) "budget notification $notificationName has an incorrect threshold type"
        Assert-True ($null -ne $notification -and $notification.contactGroups.Count -eq 1) "budget notification $notificationName must target the ScentIQ action group"
    }

    $resourceGroupTagUpdate = @($resources | Where-Object {
        $_.type -eq 'Microsoft.Resources/tags' -and
        ($_.properties.tags -is [string] -and $_.properties.tags -match '^\[union\(.+\)\]$')
    }) | Select-Object -First 1
    Assert-True ($null -ne $resourceGroupTagUpdate) 'resource group tags must merge existing tags with the required common tags'

    $resourceGroupDeclarations = @($resources | Where-Object { $_.type -eq 'Microsoft.Resources/resourceGroups' })
    Assert-True ((@($resourceGroupDeclarations | Where-Object { $_.existing }).Count) -eq 1) 'the live development resource group must be declared as existing'
    Assert-True ((@($resourceGroupDeclarations | Where-Object { -not $_.existing }).Count) -eq 0) 'the live development resource group must not be emitted as a tagless PUT'

    $adoptedTaggableTypes = @(
        'Microsoft.OperationalInsights/workspaces',
        'Microsoft.ManagedIdentity/userAssignedIdentities',
        'Microsoft.ContainerRegistry/registries',
        'Microsoft.Storage/storageAccounts',
        'Microsoft.KeyVault/vaults',
        'Microsoft.DBforPostgreSQL/flexibleServers',
        'Microsoft.App/managedEnvironments'
    )
    $adoptedResources = @($resources | Where-Object { $_.type -in $adoptedTaggableTypes -and $_.existing })
    Assert-True ((@($adoptedResources.type | Sort-Object -Unique).Count) -eq $adoptedTaggableTypes.Count) 'every adopted taggable resource type must be declared as existing'
    $adoptionTagMerges = @($resources | Where-Object {
        $_.type -eq 'Microsoft.Resources/tags' -and
        ($_.properties.tags -is [string] -and $_.properties.tags -match '^\[union\(.+\)\]$')
    })
    Assert-True ($adoptionTagMerges.Count -ge ($adoptedTaggableTypes.Count + 1)) 'every adopted taggable resource type must receive a merge-safe tag update'
    Assert-True ((@($adoptionTagMerges | Where-Object { $null -ne $_.scope }).Count) -ge $adoptedTaggableTypes.Count) 'every adopted resource tag update must target that resource scope'

    $registryDeclarations = @($resources | Where-Object { $_.type -eq 'Microsoft.ContainerRegistry/registries' })
    $registryCreate = @($registryDeclarations | Where-Object { -not $_.existing }) | Select-Object -First 1
    Assert-True ($null -ne $registryCreate -and $registryCreate.condition -match '^\[not\(parameters\(''useExisting''\)\)\]$') 'registry creation must be disabled for the adoption path'

    $platformDeployment = @($resources | Where-Object { $_.type -eq 'Microsoft.Resources/deployments' -and $_.name -match 'platform-' }) | Select-Object -First 1
    $platformActionGroupId = $platformDeployment.properties.parameters.actionGroupId.value
    Assert-True ($null -ne $platformDeployment -and $platformActionGroupId -is [string]) 'platform deployment must retain the actionGroupId interface'
    Assert-True ($platformActionGroupId -is [string] -and $platformActionGroupId -match 'Microsoft\.Insights/actionGroups.+scentiq-ag') 'platform actionGroupId must be a deterministic action group resource ID'
    Assert-True ($platformActionGroupId -is [string] -and $platformActionGroupId -notmatch 'reference\(') 'platform actionGroupId must not depend on the governance deployment output'

    Assert-True ($null -ne $platformDeployment -and $null -eq $platformDeployment.condition) 'platform deployment must remain unconditioned so Azure validates its adopted resources'
    Assert-True ($null -ne $platformDeployment -and $platformDeployment.properties.parameters.useExistingFoundation.value -eq "[parameters('useExistingFoundation')]") 'platform must forward the requested foundation mode without creating a conditional nested deployment'
    $platformRegistryOutput = $platformDeployment.properties.template.outputs.registryLoginServer.value
    Assert-True ($platformRegistryOutput -is [string] -and $platformRegistryOutput -notmatch 'reference\(') 'platform registry output must be deterministic and must not force conditional module output evaluation'

    $foundationRoleAssignmentDeployments = @($resources | Where-Object {
        $_.type -eq 'Microsoft.Resources/deployments' -and
        $_.name -match '(registry|storage|key-vault)-(adopt|create)-'
    })
    Assert-True ($foundationRoleAssignmentDeployments.Count -eq 0) 'foundation resource modules must not hide conditional role assignment branches from subscription validation'

    $adoptedFoundationRoleAssignments = @($resources | Where-Object {
        $_.type -eq 'Microsoft.Authorization/roleAssignments' -and
        $_.condition -match "^\[parameters\('useExistingFoundation'\)\]$" -and
        $_.properties.principalId -eq "[parameters('identityPrincipalId')]"
    })
    Assert-True ($adoptedFoundationRoleAssignments.Count -ge 1) 'adopted foundation role assignments must use the adoption-only identityPrincipalId directly'

    $freshFoundationRoleAssignments = @($resources | Where-Object {
        $_.type -eq 'Microsoft.Authorization/roleAssignments' -and
        $_.condition -match "^\[not\(parameters\('useExistingFoundation'\)\)\]$" -and
        $_.properties.principalId -is [string] -and
        $_.properties.principalId -match "reference\('identity'\)\.outputs\.principalId\.value"
    })
    Assert-True ($freshFoundationRoleAssignments.Count -ge 3) 'fresh foundation role assignments must use the newly created identity principal ID directly'

    $requiredTags = @(
        'application',
        'environment',
        'owner',
        'cost-center',
        'managed-by',
        'data-classification'
    )
    $taggableTypes = @(
        'Microsoft.OperationalInsights/workspaces',
        'Microsoft.Insights/components',
        'Microsoft.ManagedIdentity/userAssignedIdentities',
        'Microsoft.ContainerRegistry/registries',
        'Microsoft.Storage/storageAccounts',
        'Microsoft.KeyVault/vaults',
        'Microsoft.DBforPostgreSQL/flexibleServers',
        'Microsoft.App/managedEnvironments',
        'Microsoft.App/containerApps',
        'Microsoft.App/jobs',
        'Microsoft.Insights/actionGroups'
    )
    foreach ($resource in @($resources | Where-Object { $_.type -in $taggableTypes -and -not $_.existing })) {
        $usesTagExpression = $resource.tags -is [string] -and $resource.tags -match '^\[.+\]$'
        foreach ($tag in $requiredTags) {
            Assert-True ($usesTagExpression -or ($null -ne $resource.tags -and $null -ne $resource.tags.$tag)) "resource $($resource.type) is missing required tag $tag"
        }
    }
}

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    exit 1
}
