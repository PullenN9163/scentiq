param(
    [Parameter(Mandatory)] [string] $TemplatePath,
    [Parameter(Mandatory)] [ValidateSet('dev', 'test', 'prod-reference')] [string] $Mode,
    [string] $ParametersPath
)

$template = Get-Content -Raw -LiteralPath $TemplatePath | ConvertFrom-Json -Depth 100
$deploymentParameters = if ($ParametersPath -and (Test-Path -LiteralPath $ParametersPath)) {
    (Get-Content -Raw -LiteralPath $ParametersPath | ConvertFrom-Json -Depth 100).parameters
}
else {
    $null
}
$failures = [System.Collections.Generic.List[string]]::new()
$roleDefinitionExpressions = @{}

function Assert-True([bool] $Condition, [string] $Message) {
    if (-not $Condition) { $script:failures.Add($Message) }
}

function Get-PropertyPathValue([object] $Object, [string] $Path) {
    $current = $Object
    foreach ($segment in $Path.Split('.')) {
        if ($null -eq $current -or $null -eq $current.PSObject.Properties[$segment]) {
            return @{ Found = $false; Value = $null }
        }
        $current = $current.PSObject.Properties[$segment].Value
    }

    return @{ Found = $true; Value = $current }
}

function Assert-PreservationBaseline([object] $Resource, [hashtable] $Expected, [string] $Label) {
    foreach ($path in $Expected.Keys) {
        $actual = Get-PropertyPathValue $Resource $path
        Assert-True ($actual.Found -and $actual.Value -eq $Expected[$path]) "$Label must explicitly preserve $path"
    }
}

function Assert-EmptyArrayProperty([object] $Resource, [string] $Path, [string] $Label) {
    $actual = Get-PropertyPathValue $Resource $Path
    Assert-True ($actual.Found -and @($actual.Value).Count -eq 0) "$Label must explicitly preserve an empty $Path collection"
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

$restoreScriptPath = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) 'scripts/azure/Test-PostgresRestore.ps1'
if (-not (Test-Path -LiteralPath $restoreScriptPath)) {
    $failures.Add('PostgreSQL restore drill script is missing')
}
else {
    $invalidRestoreNameOutput = & $restoreScriptPath -ResourceGroupName 'scentiq-rg-dev-eus' -ServerName 'scentiq-pg-dev-eus' -RestoreServerName 'invalid-restore-target' -RestorePoint '2026-08-29T00:00:00Z' -ExpectedDatabaseName 'scentiq_dev' -TargetResourceGroupName 'scentiq-rg-test-eus' 2>&1
    Assert-True ($LASTEXITCODE -eq 1 -and ($invalidRestoreNameOutput | Out-String) -match 'scentiq-pg-restore-') 'the PostgreSQL restore drill must reject a restore name outside the approved prefix before invoking Azure'
    $global:LASTEXITCODE = 0

    $invalidTargetGroupOutput = & $restoreScriptPath -ResourceGroupName 'scentiq-rg-dev-eus' -ServerName 'scentiq-pg-dev-eus' -RestoreServerName 'scentiq-pg-restore-guardrail' -RestorePoint '2026-08-29T00:00:00Z' -ExpectedDatabaseName 'scentiq_dev' -TargetResourceGroupName 'scentiq-rg-dev-eus' 2>&1
    Assert-True ($LASTEXITCODE -eq 1 -and ($invalidTargetGroupOutput | Out-String) -match 'scentiq-rg-test-eus') 'the PostgreSQL restore drill must reject a restore resource group other than the explicit test resource group before invoking Azure'
    $global:LASTEXITCODE = 0

    $overlappingTargetOutput = & $restoreScriptPath -ResourceGroupName 'scentiq-rg-test-eus' -ServerName 'scentiq-pg-restore-overlap' -RestoreServerName 'scentiq-pg-restore-overlap' -RestorePoint '2026-08-29T00:00:00Z' -ExpectedDatabaseName 'scentiq_dev' -TargetResourceGroupName 'scentiq-rg-test-eus' 2>&1
    Assert-True ($LASTEXITCODE -eq 1 -and ($overlappingTargetOutput | Out-String) -match 'same resource') 'the PostgreSQL restore drill must reject a source and target that identify the same resource before invoking Azure'
    $global:LASTEXITCODE = 0

    $futureRestorePointOutput = & $restoreScriptPath -ResourceGroupName 'scentiq-rg-dev-eus' -ServerName 'scentiq-pg-dev-eus' -RestoreServerName 'scentiq-pg-restore-future' -RestorePoint '2999-01-01T00:00:00Z' -ExpectedDatabaseName 'scentiq_dev' -TargetResourceGroupName 'scentiq-rg-test-eus' 2>&1
    Assert-True ($LASTEXITCODE -eq 1 -and ($futureRestorePointOutput | Out-String) -match 'must not be in the future') 'the PostgreSQL restore drill must reject a future restore point before invoking Azure'
    $global:LASTEXITCODE = 0

    $unconfirmedCleanupOutput = & $restoreScriptPath -ResourceGroupName 'scentiq-rg-dev-eus' -ServerName 'scentiq-pg-dev-eus' -RestoreServerName 'scentiq-pg-restore-guardrail' -RestorePoint '2026-08-29T00:00:00Z' -ExpectedDatabaseName 'scentiq_dev' -TargetResourceGroupName 'scentiq-rg-test-eus' -CleanupOnly 2>&1
    Assert-True ($LASTEXITCODE -eq 1 -and ($unconfirmedCleanupOutput | Out-String) -match 'requires the explicit DeleteAfterVerification') 'the PostgreSQL restore drill must require an explicit deletion confirmation for cleanup'
    $global:LASTEXITCODE = 0

    $loneDeleteConfirmationOutput = & $restoreScriptPath -ResourceGroupName 'scentiq-rg-dev-eus' -ServerName 'scentiq-pg-dev-eus' -RestoreServerName 'scentiq-pg-restore-lone-delete' -RestorePoint '2999-01-01T00:00:00Z' -ExpectedDatabaseName 'scentiq_dev' -TargetResourceGroupName 'scentiq-rg-test-eus' -DeleteAfterVerification 2>&1
    Assert-True ($LASTEXITCODE -eq 1 -and ($loneDeleteConfirmationOutput | Out-String) -match 'requires CleanupOnly') 'the PostgreSQL restore drill must reject DeleteAfterVerification unless CleanupOnly is explicitly supplied before Azure is invoked'
    $global:LASTEXITCODE = 0

    $restoreScriptContent = Get-Content -Raw -LiteralPath $restoreScriptPath
    Assert-True ($restoreScriptContent -match 'backup\.earliestRestoreDate' -and $restoreScriptContent -match 'Assert-TargetServerAbsent') 'the PostgreSQL restore drill must query the source retention boundary and require an absent target before restoring'
    Assert-True (([regex]::Matches($restoreScriptContent, "'postgres', 'flexible-server', 'delete'")).Count -eq 1) 'the PostgreSQL restore drill must contain a delete invocation only in its cleanup-only path'
    Assert-True ($restoreScriptContent -match "To delete this validated restore target, run exactly:" -and $restoreScriptContent -match '-CleanupOnly -DeleteAfterVerification') 'the PostgreSQL restore drill must print the exact separate guarded cleanup invocation after validation'
}

$recoveryRunbookPath = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) 'docs/runbooks/azure-recovery.md'
if (-not (Test-Path -LiteralPath $recoveryRunbookPath)) {
    $failures.Add('Azure recovery runbook is missing')
}
else {
    $recoveryRunbook = Get-Content -Raw -LiteralPath $recoveryRunbookPath
    Assert-True ($recoveryRunbook -match 'PreflightOnly' -and $recoveryRunbook -match 'CleanupOnly' -and $recoveryRunbook -match 'DeleteAfterVerification') 'the Azure recovery runbook must document guarded PostgreSQL preflight and confirmed cleanup'
    Assert-True ($recoveryRunbook -notmatch 'az postgres flexible-server (restore|delete)') 'the Azure recovery runbook must not provide an unguarded PostgreSQL restore or delete command'
}

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
    $adoptedAssignmentExpressions = @($adoptedAssignmentNames | ForEach-Object { "[parameters('$_')]" })
    $nonAdoptedAssignments = @($roleAssignments | Where-Object { $_.name -notin $adoptedAssignmentExpressions })
    Assert-True ((@($nonAdoptedAssignments | Where-Object { $_.name -notmatch 'guid\(' }).Count) -eq 0) 'fresh API and new workload role assignment names must be deterministic GUID expressions'
    Assert-True ($webAssignments.Count -eq 1 -and $webAssignments[0].name -match 'guid\(') 'web AcrPull assignment must use a deterministic GUID name'
    Assert-True ($migrationAssignments.Count -eq 2 -and @($migrationAssignments | Where-Object { $_.name -notmatch 'guid\(' }).Count -eq 0) 'migration role assignments must use deterministic GUID names'
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
        'Microsoft.DBforPostgreSQL/flexibleServers',
        'Microsoft.App/managedEnvironments'
    )
    $adoptedResources = @($resources | Where-Object { $_.type -in $adoptedTaggableTypes -and $_.existing })
    Assert-True ((@($adoptedResources.type | Sort-Object -Unique).Count) -eq $adoptedTaggableTypes.Count) 'every adopted taggable resource type must be declared as existing'
    $adoptionTagMerges = @($resources | Where-Object {
        $_.type -eq 'Microsoft.Resources/tags' -and
        ($_.properties.tags -is [string] -and $_.properties.tags -match '^\[union\(.+\)\]$')
    })

    $postgresDeployment = @($resources | Where-Object { $_.type -eq 'Microsoft.Resources/deployments' -and $_.name -match 'postgres-' }) | Select-Object -First 1
    Assert-True ($null -ne $postgresDeployment -and $postgresDeployment.properties.parameters.serverName.value -eq "[parameters('postgresServerName')]") 'the PostgreSQL module must receive the exact adopted server name'
    Assert-True ($null -ne $postgresDeployment -and $postgresDeployment.properties.parameters.location.value -eq "[parameters('postgresLocation')]") 'the PostgreSQL module must receive the exact adopted server location'
    $postgresServers = @($resources | Where-Object { $_.type -eq 'Microsoft.DBforPostgreSQL/flexibleServers' -and -not $_.existing })
    $freshPostgresDeployment = @($resources | Where-Object { $_.type -eq 'Microsoft.Resources/deployments' -and $_.name -eq 'postgres-fresh-server' }) | Select-Object -First 1
    $freshPostgresServer = @($postgresServers | Where-Object { $_.condition -ne "[parameters('useExisting')]" }) | Select-Object -First 1
    $adoptedPostgresServer = @($postgresServers | Where-Object { $_.condition -eq "[parameters('useExisting')]" }) | Select-Object -First 1
    Assert-True ($postgresServers.Count -eq 2 -and $null -ne $freshPostgresDeployment -and $freshPostgresDeployment.condition -eq "[not(parameters('useExisting'))]" -and $null -ne $freshPostgresServer -and $null -ne $adoptedPostgresServer) 'PostgreSQL must model distinct fresh-create and adopted in-place paths without duplicate parent PUTs'
    foreach ($postgresServer in @($freshPostgresServer, $adoptedPostgresServer)) {
        Assert-True ($null -ne $postgresServer -and $postgresServer.name -eq "[parameters('serverName')]") 'PostgreSQL must retain the exact server resource path'
        Assert-True ($null -ne $postgresServer -and $postgresServer.location -eq "[parameters('location')]") 'PostgreSQL must retain the exact server location'
        Assert-PreservationBaseline $postgresServer @{
            'sku.name' = "[parameters('skuName')]"
            'sku.tier' = 'Burstable'
            'properties.version' = '18'
            'properties.storage.storageSizeGB' = 32
            'properties.storage.autoGrow' = 'Enabled'
            'properties.backup.backupRetentionDays' = 14
            'properties.backup.geoRedundantBackup' = 'Disabled'
            'properties.network.publicNetworkAccess' = 'Enabled'
            'properties.highAvailability.mode' = 'Disabled'
            'properties.maintenanceWindow.customWindow' = 'Enabled'
            'properties.maintenanceWindow.dayOfWeek' = 0
            'properties.maintenanceWindow.startHour' = 7
            'properties.maintenanceWindow.startMinute' = 0
            'properties.authConfig.activeDirectoryAuth' = 'Enabled'
            'properties.authConfig.passwordAuth' = 'Enabled'
            'properties.authConfig.tenantId' = "[parameters('tenantId')]"
            'properties.dataEncryption.type' = 'SystemManaged'
        } 'the PostgreSQL preservation baseline'
    }
    Assert-True ($null -ne $freshPostgresServer -and $freshPostgresServer.properties.PSObject.Properties['administratorLogin'] -and $freshPostgresServer.properties.PSObject.Properties['administratorLoginPassword']) 'the fresh PostgreSQL path must accept administrator credentials only during creation'
    Assert-True ($null -ne $adoptedPostgresServer -and -not $adoptedPostgresServer.properties.PSObject.Properties['administratorLogin'] -and -not $adoptedPostgresServer.properties.PSObject.Properties['administratorLoginPassword'] -and -not $adoptedPostgresServer.PSObject.Properties['identity']) 'the adopted PostgreSQL path must not update administrator credentials or identity'
    Assert-PreservationBaseline $adoptedPostgresServer @{
        'properties.storage.iops' = 120
        'properties.storage.tier' = 'P4'
        'properties.storage.type' = 'Premium_LRS'
        'properties.replica.role' = 'Primary'
        'properties.replicationRole' = 'Primary'
    } 'the adopted PostgreSQL preservation baseline'

    $postgresDatabases = @($resources | Where-Object { $_.type -eq 'Microsoft.DBforPostgreSQL/flexibleServers/databases' })
    $scentiqDatabase = $postgresDatabases | Where-Object { $_.name -eq "[format('{0}/{1}', parameters('serverName'), 'scentiq_dev')]" } | Select-Object -First 1
    Assert-True ($postgresDatabases.Count -eq 1 -and $null -ne $scentiqDatabase -and $scentiqDatabase.properties.charset -eq 'UTF8' -and $scentiqDatabase.properties.collation -eq 'en_US.utf8') 'PostgreSQL must manage only the scentiq_dev database with its observed collation'

    $postgresConfigurations = @($resources | Where-Object { $_.type -eq 'Microsoft.DBforPostgreSQL/flexibleServers/configurations' })
    $tlsConfiguration = $postgresConfigurations | Where-Object { $_.name -eq "[format('{0}/{1}', parameters('serverName'), 'require_secure_transport')]" } | Select-Object -First 1
    Assert-True ($postgresConfigurations.Count -eq 1 -and $null -ne $tlsConfiguration -and $tlsConfiguration.properties.value -eq 'on') 'PostgreSQL must require TLS without taking ownership of unrelated server configurations'

    $postgresFirewallRules = @($resources | Where-Object { $_.type -eq 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules' })
    $azureServicesRule = $postgresFirewallRules | Select-Object -First 1
    $allowAzureServicesRuleExpression = "[and(equals(parameters('deploymentMode'), 'dev'), equals(parameters('networkMode'), 'publicDev'))]"
    Assert-True ($null -ne $postgresDeployment -and $postgresDeployment.properties.parameters.azureServicesFirewallRuleName.value -eq "[parameters('postgresAzureServicesFirewallRuleName')]") 'the PostgreSQL module must receive the exact adopted Azure-services firewall rule name'
    Assert-True ($null -ne $azureServicesRule -and $azureServicesRule.name -eq "[format('{0}/{1}', parameters('serverName'), parameters('azureServicesFirewallRuleName'))]") 'PostgreSQL must preserve the exact adopted Azure-services firewall rule resource path'
    if ($Mode -eq 'dev') {
        Assert-True ($postgresFirewallRules.Count -eq 1 -and $null -ne $azureServicesRule -and $azureServicesRule.condition -eq "[parameters('allowAzureServicesFirewallRule')]" -and $postgresDeployment.properties.parameters.allowAzureServicesFirewallRule.value -eq $allowAzureServicesRuleExpression -and $azureServicesRule.properties.startIpAddress -eq '0.0.0.0' -and $azureServicesRule.properties.endIpAddress -eq '0.0.0.0') 'development PostgreSQL networking must declare only the exact Azure-services firewall rule'
    }
    else {
        Assert-True ($postgresFirewallRules.Count -eq 1 -and $null -ne $azureServicesRule -and $azureServicesRule.condition -eq "[parameters('allowAzureServicesFirewallRule')]" -and $postgresDeployment.properties.parameters.allowAzureServicesFirewallRule.value -eq $allowAzureServicesRuleExpression -and $deploymentParameters.deploymentMode.value -ne 'dev') 'test and production-reference PostgreSQL networking must reject the Azure-services firewall rule'
    }
    Assert-True (@($postgresFirewallRules | Where-Object { $_.properties.startIpAddress -eq '0.0.0.0' -and $_.properties.endIpAddress -eq '255.255.255.255' }).Count -eq 0) 'PostgreSQL must not declare an unrestricted IPv4 firewall rule'

    $postgresDiagnostic = @($resources | Where-Object { $_.type -eq 'Microsoft.Insights/diagnosticSettings' -and $_.name -eq 'scentiq-postgres-diagnostics' }) | Select-Object -First 1
    Assert-True ($null -ne $postgresDiagnostic -and $postgresDiagnostic.scope -eq "[resourceId('Microsoft.DBforPostgreSQL/flexibleServers', parameters('serverName'))]" -and $postgresDiagnostic.properties.workspaceId -eq "[parameters('workspaceResourceId')]") 'PostgreSQL diagnostics must target the adopted server and Log Analytics workspace'
    Assert-True ($null -ne $postgresDiagnostic -and $postgresDiagnostic.properties.logs.Count -eq 1 -and $postgresDiagnostic.properties.logs[0].categoryGroup -eq 'allLogs' -and $postgresDiagnostic.properties.logs[0].enabled -eq $true -and $postgresDiagnostic.properties.metrics.Count -eq 1 -and $postgresDiagnostic.properties.metrics[0].category -eq 'AllMetrics' -and $postgresDiagnostic.properties.metrics[0].enabled -eq $true) 'PostgreSQL diagnostics must send all supported logs and metrics'

    $postgresLock = @($resources | Where-Object { $_.type -eq 'Microsoft.Authorization/locks' -and $_.name -eq 'scentiq-postgres-protection' }) | Select-Object -First 1
    Assert-True ($null -ne $postgresLock -and $postgresLock.scope -eq "[resourceId('Microsoft.DBforPostgreSQL/flexibleServers', parameters('serverName'))]" -and $postgresLock.properties.level -eq 'CanNotDelete' -and $postgresLock.condition -eq "[parameters('enablePostgresLock')]") 'PostgreSQL must model a staged CanNotDelete lock on the exact adopted server'

    $postgresOutput = $platformDeploymentForIdentityContracts.properties.template.outputs.postgres
    Assert-True ($null -ne $postgresOutput -and $postgresOutput.type -eq 'object' -and @($postgresOutput.value.PSObject.Properties.Name | Where-Object { $_ -in @('id', 'fqdn', 'databaseName', 'alertScope') }).Count -eq 4) 'platform must expose the PostgreSQL ID, FQDN, database name, and alert scope only'
    Assert-True ($null -ne $postgresOutput -and (@($postgresOutput.value.PSObject.Properties.Name | Where-Object { $_ -match '(?i)password|credential|secret|connection' }).Count -eq 0)) 'PostgreSQL outputs must not expose credentials or connection secrets'
    $postgresLockEnabledOutput = $platformDeploymentForIdentityContracts.properties.template.outputs.postgresLockEnabled
    Assert-True ($null -ne $postgresLockEnabledOutput -and $postgresLockEnabledOutput.type -eq 'bool' -and $postgresLockEnabledOutput.value -eq "[parameters('enablePostgresLock')]") 'platform must expose the staged PostgreSQL lock mode without exposing credentials'
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
        'Microsoft.DBforPostgreSQL/flexibleServers',
        'Microsoft.App/managedEnvironments',
        'Microsoft.App/containerApps',
        'Microsoft.App/jobs',
        'Microsoft.Insights/actionGroups'
    )
    foreach ($resource in @($resources | Where-Object {
                $_.type -in $taggableTypes -and
                -not $_.existing -and
                -not ($_.type -eq 'Microsoft.DBforPostgreSQL/flexibleServers' -and $_.condition -eq "[parameters('useExisting')]")
            })) {
        $usesTagExpression = $resource.tags -is [string] -and $resource.tags -match '^\[.+\]$'
        foreach ($tag in $requiredTags) {
            Assert-True ($usesTagExpression -or ($null -ne $resource.tags -and $null -ne $resource.tags.$tag)) "resource $($resource.type) is missing required tag $tag"
        }
    }

    $managedStorage = @($resources | Where-Object {
        $_.type -eq 'Microsoft.Storage/storageAccounts' -and -not $_.existing -and $null -eq $_.condition
    }) | Select-Object -First 1
    Assert-True ($null -ne $managedStorage) 'the adopted storage account must be managed in place without a conditional create path'
    $storageTagMerge = @($resources | Where-Object { $_.type -eq 'Microsoft.Resources/tags' -and $_.scope -match 'Microsoft.Storage/storageAccounts' -and $_.properties.tags -match '^\[union\(.+\)\]$' }) | Select-Object -First 1
    Assert-True ($null -ne $storageTagMerge) 'the adopted storage account must preserve existing tags through a merge-safe tag update'
    Assert-True ($null -ne $managedStorage -and $managedStorage.kind -eq 'StorageV2' -and $managedStorage.sku.name -eq 'Standard_LRS') 'the adopted storage account must preserve StorageV2 and Standard_LRS'
    Assert-True ($null -ne $managedStorage -and $managedStorage.properties.allowBlobPublicAccess -eq $false) 'storage must disable anonymous blob access'
    Assert-True ($null -ne $managedStorage -and $managedStorage.properties.minimumTlsVersion -eq 'TLS1_2' -and $managedStorage.properties.supportsHttpsTrafficOnly -eq $true -and $managedStorage.properties.publicNetworkAccess -eq 'Enabled' -and $managedStorage.properties.networkAcls.bypass -eq 'AzureServices') 'storage must preserve HTTPS, TLS 1.2, the approved dev public network access, and the existing service bypass'
    Assert-True ($null -ne $managedStorage -and $managedStorage.properties.defaultToOAuthAuthentication -eq $true) 'storage must default clients to OAuth authentication'
    Assert-True ($null -ne $managedStorage -and $managedStorage.properties.allowSharedKeyAccess -eq "[parameters('enableStorageSharedKeyAccess')]") 'storage Shared Key disablement must be modeled through the staged adoption control'
    Assert-True ($null -ne $managedStorage -and $managedStorage.name -eq "[parameters('storageName')]") 'the managed storage account must use the exact storageName adoption parameter'
    Assert-True ($null -ne $managedStorage -and $managedStorage.properties.dnsEndpointType -eq 'Standard') 'storage must preserve the current Standard DNS endpoint type'
    Assert-True ($null -ne $managedStorage -and $managedStorage.properties.encryption.keySource -eq 'Microsoft.Storage' -and $managedStorage.properties.encryption.requireInfrastructureEncryption -eq $false -and $managedStorage.properties.encryption.services.blob.enabled -eq $true -and $managedStorage.properties.encryption.services.blob.keyType -eq 'Account' -and $managedStorage.properties.encryption.services.file.enabled -eq $true -and $managedStorage.properties.encryption.services.file.keyType -eq 'Account' -and $managedStorage.properties.encryption.services.queue.keyType -eq 'Service' -and $managedStorage.properties.encryption.services.table.keyType -eq 'Service') 'storage must preserve Microsoft-managed Blob, File, Queue, and Table encryption settings'
    Assert-True ($null -ne $managedStorage -and $managedStorage.properties.networkAcls.defaultAction -eq 'Allow' -and $managedStorage.properties.networkAcls.ipRules.Count -eq 0 -and $managedStorage.properties.networkAcls.resourceAccessRules.Count -eq 0 -and $managedStorage.properties.networkAcls.virtualNetworkRules.Count -eq 0) 'storage must preserve empty IPv4, resource-access, and virtual-network ACL arrays'
    Assert-PreservationBaseline $managedStorage @{
        'kind' = 'StorageV2'
        'sku.name' = 'Standard_LRS'
        'properties.accessTier' = 'Hot'
        'properties.allowBlobPublicAccess' = $false
        'properties.allowCrossTenantReplication' = $false
        'properties.allowSharedKeyAccess' = "[parameters('enableStorageSharedKeyAccess')]"
        'properties.defaultToOAuthAuthentication' = $true
        'properties.dnsEndpointType' = 'Standard'
        'properties.encryption.keySource' = 'Microsoft.Storage'
        'properties.encryption.requireInfrastructureEncryption' = $false
        'properties.encryption.services.blob.enabled' = $true
        'properties.encryption.services.blob.keyType' = 'Account'
        'properties.encryption.services.file.enabled' = $true
        'properties.encryption.services.file.keyType' = 'Account'
        'properties.encryption.services.queue.keyType' = 'Service'
        'properties.encryption.services.table.keyType' = 'Service'
        'properties.minimumTlsVersion' = 'TLS1_2'
        'properties.networkAcls.bypass' = 'AzureServices'
        'properties.networkAcls.defaultAction' = 'Allow'
        'properties.publicNetworkAccess' = 'Enabled'
        'properties.supportsHttpsTrafficOnly' = $true
    } 'the adopted storage account preservation baseline'
    Assert-EmptyArrayProperty $managedStorage 'properties.networkAcls.ipRules' 'the adopted storage account preservation baseline'
    Assert-EmptyArrayProperty $managedStorage 'properties.networkAcls.resourceAccessRules' 'the adopted storage account preservation baseline'
    Assert-EmptyArrayProperty $managedStorage 'properties.networkAcls.virtualNetworkRules' 'the adopted storage account preservation baseline'
    Assert-True ($null -ne $managedStorage -and $managedStorage.properties.networkAcls.ipRules.Count -eq 0 -and $managedStorage.properties.networkAcls.resourceAccessRules.Count -eq 0 -and $managedStorage.properties.networkAcls.virtualNetworkRules.Count -eq 0) 'the adopted storage account preservation baseline must retain observed empty ACL collections'

    $blobService = @($resources | Where-Object { $_.type -eq 'Microsoft.Storage/storageAccounts/blobServices' }) | Select-Object -First 1
    Assert-True ($null -ne $blobService -and $blobService.properties.isVersioningEnabled -eq $true -and $blobService.properties.changeFeed.enabled -eq $true) 'the Blob service must enable versioning and change feed'
    Assert-True ($null -ne $blobService -and $blobService.properties.deleteRetentionPolicy.enabled -eq $true -and $blobService.properties.deleteRetentionPolicy.days -eq 14) 'the Blob service must retain soft-deleted blobs for fourteen days'
    Assert-True ($null -ne $blobService -and $blobService.properties.containerDeleteRetentionPolicy.enabled -eq $true -and $blobService.properties.containerDeleteRetentionPolicy.days -eq 14) 'the Blob service must retain soft-deleted containers for fourteen days'
    Assert-True ($null -ne $blobService -and $blobService.name -match "parameters\('storageName'\).+'default'") 'the Blob service must be the default child of the adopted storage account'
    Assert-True ($null -ne $blobService -and $blobService.properties.cors.corsRules.Count -eq 0) 'the Blob service must preserve the observed empty CORS rule set'
    Assert-PreservationBaseline $blobService @{
        'properties.changeFeed.enabled' = $true
        'properties.containerDeleteRetentionPolicy.enabled' = $true
        'properties.containerDeleteRetentionPolicy.days' = 14
        'properties.deleteRetentionPolicy.allowPermanentDelete' = $false
        'properties.deleteRetentionPolicy.enabled' = $true
        'properties.deleteRetentionPolicy.days' = 14
        'properties.isVersioningEnabled' = $true
    } 'the Blob service preservation baseline'

    $storageContainers = @($resources | Where-Object { $_.type -eq 'Microsoft.Storage/storageAccounts/blobServices/containers' })
    Assert-True ($storageContainers.Count -eq 3 -and @($storageContainers | Where-Object { -not $_.existing }).Count -eq 0) 'existing private Blob containers must use adoption references so deployment does not reset container metadata'
    foreach ($containerName in @('uploads', 'exports', 'system')) {
        Assert-True ((@($storageContainers | Where-Object { $_.name -match [regex]::Escape("'$containerName'") }).Count) -eq 1) "storage must declare the $containerName container"
    }

    $storagePolicy = @($resources | Where-Object { $_.type -eq 'Microsoft.Storage/storageAccounts/managementPolicies' }) | Select-Object -First 1
    Assert-True ($null -ne $storagePolicy -and $storagePolicy.properties.policy.rules.Count -eq 1) 'storage must use one scoped lifecycle policy rule and rely on Azure garbage collection for uncommitted blocks'
    $temporaryExportsRule = $storagePolicy.properties.policy.rules | Where-Object { $_.name -eq 'delete-temporary-exports-after-seven-days' } | Select-Object -First 1
    Assert-True ($null -ne $temporaryExportsRule -and $temporaryExportsRule.definition.filters.prefixMatch.Count -eq 1 -and $temporaryExportsRule.definition.filters.prefixMatch[0] -eq 'exports/temporary/' -and $temporaryExportsRule.definition.actions.baseBlob.delete.daysAfterModificationGreaterThan -eq 7) 'storage lifecycle deletion must be limited to temporary exports after seven days'

    $newKeyVault = @($resources | Where-Object {
        $_.type -eq 'Microsoft.KeyVault/vaults' -and -not $_.existing -and $_.condition -eq "[not(parameters('useExisting'))]"
    }) | Select-Object -First 1
    Assert-True ($null -ne $newKeyVault -and $newKeyVault.properties.sku.name -eq 'standard') 'the fresh Key Vault path must use the standard SKU'
    $keyVaultTagMerge = @($resources | Where-Object { $_.type -eq 'Microsoft.Resources/tags' -and $_.scope -match 'Microsoft.KeyVault/vaults' -and $_.properties.tags -match '^\[union\(.+\)\]$' }) | Select-Object -First 1
    Assert-True ($null -ne $keyVaultTagMerge) 'the adopted Key Vault must preserve existing tags through a merge-safe tag update'
    Assert-True ($null -ne $newKeyVault -and $newKeyVault.properties.enableRbacAuthorization -eq $true -and $newKeyVault.properties.enablePurgeProtection -eq $true -and $newKeyVault.properties.enableSoftDelete -eq $true -and $newKeyVault.properties.softDeleteRetentionInDays -eq 7) 'the fresh Key Vault path must use RBAC, purge protection, and seven-day soft delete retention'
    Assert-True ($null -ne $newKeyVault -and $newKeyVault.properties.publicNetworkAccess -eq 'Enabled') 'the fresh Key Vault path must preserve approved dev public network access'
    $adoptedKeyVault = @($resources | Where-Object { $_.type -eq 'Microsoft.KeyVault/vaults' -and $_.existing -and $null -eq $_.condition -and $_.name -eq "[parameters('vaultName')]" }) | Select-Object -First 1
    Assert-True ($null -ne $adoptedKeyVault -and $adoptedKeyVault.name -eq "[parameters('vaultName')]") 'the unchanged adopted Key Vault must use an unconditional existing reference'
    Assert-True ($null -ne $newKeyVault -and $newKeyVault.name -eq "[parameters('vaultName')]") 'the fresh Key Vault path must use the exact vaultName parameter'
    Assert-True ($null -ne $newKeyVault -and $newKeyVault.properties.accessPolicies.Count -eq 0 -and $newKeyVault.properties.enabledForDeployment -eq $false -and $newKeyVault.properties.enabledForDiskEncryption -eq $false -and $newKeyVault.properties.enabledForTemplateDeployment -eq $false) 'the fresh Key Vault path must use the RBAC-only access-policy and deployment-flag state'
    Assert-True ($null -ne $newKeyVault -and $newKeyVault.properties.networkAcls.bypass -eq 'None' -and $newKeyVault.properties.networkAcls.defaultAction -eq 'Allow' -and $newKeyVault.properties.networkAcls.ipRules.Count -eq 0 -and $newKeyVault.properties.networkAcls.virtualNetworkRules.Count -eq 0) 'the fresh Key Vault path must use the approved network ACL configuration'
    Assert-PreservationBaseline $newKeyVault @{
        'properties.enablePurgeProtection' = $true
        'properties.enableRbacAuthorization' = $true
        'properties.enableSoftDelete' = $true
        'properties.enabledForDeployment' = $false
        'properties.enabledForDiskEncryption' = $false
        'properties.enabledForTemplateDeployment' = $false
        'properties.networkAcls.bypass' = 'None'
        'properties.networkAcls.defaultAction' = 'Allow'
        'properties.publicNetworkAccess' = 'Enabled'
        'properties.softDeleteRetentionInDays' = 7
        'properties.sku.name' = 'standard'
    } 'the Key Vault fresh-create preservation baseline'
    Assert-True ($null -ne $newKeyVault -and $newKeyVault.properties.accessPolicies.Count -eq 0 -and $newKeyVault.properties.networkAcls.ipRules.Count -eq 0 -and $newKeyVault.properties.networkAcls.virtualNetworkRules.Count -eq 0) 'the Key Vault preservation baseline must retain observed empty access-policy and ACL collections'

    $diagnosticSettings = @($resources | Where-Object { $_.type -eq 'Microsoft.Insights/diagnosticSettings' })
    Assert-True ($diagnosticSettings.Count -eq 3 -and @($diagnosticSettings | Where-Object { $_.properties.workspaceId -ne "[parameters('workspaceResourceId')]" }).Count -eq 0) 'Storage, Key Vault, and PostgreSQL diagnostics must target the Log Analytics workspace'
    Assert-True (@($diagnosticSettings | Where-Object { $_.properties.logs.Count -lt 1 }).Count -eq 0) 'Storage, Key Vault, and PostgreSQL diagnostics must enable logs'
    $storageDiagnostic = $diagnosticSettings | Where-Object { $_.name -eq 'scentiq-storage-audit' } | Select-Object -First 1
    $keyVaultDiagnostic = $diagnosticSettings | Where-Object { $_.name -eq 'scentiq-key-vault-audit' } | Select-Object -First 1
    Assert-True ($null -ne $storageDiagnostic -and $storageDiagnostic.scope -eq "[resourceId('Microsoft.Storage/storageAccounts', parameters('storageName'))]") 'storage diagnostics must target the adopted storage account scope'
    Assert-True ($null -ne $keyVaultDiagnostic -and $keyVaultDiagnostic.scope -eq "[resourceId('Microsoft.KeyVault/vaults', parameters('vaultName'))]") 'Key Vault diagnostics must target the adopted vault scope'

    $foundationLocks = @($resources | Where-Object { $_.type -eq 'Microsoft.Authorization/locks' -and $_.name -in @('scentiq-storage-protection', 'scentiq-key-vault-protection') })
    Assert-True ($foundationLocks.Count -eq 2 -and @($foundationLocks | Where-Object { $_.properties.level -ne 'CanNotDelete' }).Count -eq 0) 'Storage and Key Vault must model CanNotDelete locks'
    Assert-True (@($foundationLocks | Where-Object { $_.condition -ne "[parameters('enableFoundationLocks')]" }).Count -eq 0) 'foundation locks must be controlled by the staged adoption parameter'
    $storageLock = $foundationLocks | Where-Object { $_.name -eq 'scentiq-storage-protection' } | Select-Object -First 1
    $keyVaultLock = $foundationLocks | Where-Object { $_.name -eq 'scentiq-key-vault-protection' } | Select-Object -First 1
    Assert-True ($null -ne $storageLock -and $storageLock.scope -eq "[resourceId('Microsoft.Storage/storageAccounts', parameters('storageName'))]") 'storage lock must target the adopted storage account scope'
    Assert-True ($null -ne $keyVaultLock -and $keyVaultLock.scope -eq "[resourceId('Microsoft.KeyVault/vaults', parameters('vaultName'))]") 'Key Vault lock must target the adopted vault scope'

    $platformStorageOutput = $platformDeployment.properties.template.outputs.storage
    Assert-True ($null -ne $platformStorageOutput -and $platformStorageOutput.type -eq 'object' -and @($platformStorageOutput.value.PSObject.Properties.Name | Where-Object { $_ -in @('id', 'blobEndpoint', 'containerIds') }).Count -eq 3) 'platform must expose storage ID, Blob endpoint, and container resource IDs'
    $platformKeyVaultOutput = $platformDeployment.properties.template.outputs.keyVault
    Assert-True ($null -ne $platformKeyVaultOutput -and $platformKeyVaultOutput.type -eq 'object' -and @($platformKeyVaultOutput.value.PSObject.Properties.Name | Where-Object { $_ -in @('id', 'uri') }).Count -eq 2) 'platform must expose Key Vault ID and URI'
    $storageDeployment = @($resources | Where-Object { $_.type -eq 'Microsoft.Resources/deployments' -and $_.name -match "storage-" }) | Select-Object -First 1
    foreach ($containerName in @('uploads', 'exports', 'system')) {
        Assert-True ($null -ne $storageDeployment -and $storageDeployment.properties.template.outputs.containerIds.value.$containerName -eq "[resourceId('Microsoft.Storage/storageAccounts/blobServices/containers', parameters('storageName'), 'default', '$containerName')]") "storage output must resolve the $containerName declared container resource ID"
    }
    $keyVaultDeployment = @($resources | Where-Object { $_.type -eq 'Microsoft.Resources/deployments' -and $_.name -match "key-vault-" }) | Select-Object -First 1
    Assert-True ($null -ne $keyVaultDeployment -and $keyVaultDeployment.properties.template.outputs.id.value -eq "[resourceId('Microsoft.KeyVault/vaults', parameters('vaultName'))]" -and $keyVaultDeployment.properties.template.outputs.uri.value -match "if\(parameters\('useExisting'\), reference\('existingVault'\)\.vaultUri, reference\('newVault'\)\.vaultUri\)") 'Key Vault module outputs must resolve to the adopted vault ID and URI'

    $compiledTemplate = $template | ConvertTo-Json -Depth 100
    Assert-True ((@($resources | Where-Object { $_.type -eq 'Microsoft.KeyVault/vaults/secrets' }).Count) -eq 0) 'Bicep must not declare a Key Vault secret or its value'
    Assert-True ($compiledTemplate -notmatch '(?i)database-url.+value') 'Bicep must not declare a Key Vault secret value'
    Assert-True ($platformDeployment.properties.template.parameters.enableStorageSharedKeyAccess.defaultValue -eq $false) 'the secure desired state must disable Storage Shared Key access by default in the platform model'
    Assert-True ($platformDeployment.properties.template.parameters.enableFoundationLocks.defaultValue -eq $true) 'the secure desired state must enable foundation locks by default in the platform model'
    Assert-True ($platformDeployment.properties.template.parameters.enablePostgresLock.defaultValue -eq $true) 'the secure desired state must enable the PostgreSQL lock by default in the platform model'
    Assert-True ($template.parameters.enableStorageSharedKeyAccess.defaultValue -eq $false -and $template.parameters.enableFoundationLocks.defaultValue -eq $true -and $template.parameters.enablePostgresLock.defaultValue -eq $true) 'the subscription template must retain secure staged-control defaults'
    Assert-True ($null -ne $deploymentParameters) 'dev verifier runs must receive compiled development parameters'
    Assert-True ($null -ne $deploymentParameters -and $deploymentParameters.enableStorageSharedKeyAccess.value -eq $true -and $deploymentParameters.enableFoundationLocks.value -eq $false -and $deploymentParameters.enablePostgresLock.value -eq $false) 'development parameters must explicitly retain Shared Key access and defer foundation and PostgreSQL locks during staged adoption'
}

# PostgreSQL contracts must run for every requested mode. Keeping these checks
# outside the development-only adoption assertions prevents test and production
# reference validation from silently skipping recovery safeguards.
$platformDeployment = @($resources | Where-Object { $_.type -eq 'Microsoft.Resources/deployments' -and $_.name -match 'platform-' }) | Select-Object -First 1
$postgresDeployment = @($resources | Where-Object { $_.type -eq 'Microsoft.Resources/deployments' -and $_.name -match 'postgres-' }) | Select-Object -First 1
$postgresServers = @($resources | Where-Object { $_.type -eq 'Microsoft.DBforPostgreSQL/flexibleServers' -and -not $_.existing })
$freshPostgresServer = @($postgresServers | Where-Object { $_.condition -ne "[parameters('useExisting')]" }) | Select-Object -First 1
$adoptedPostgresServer = @($postgresServers | Where-Object { $_.condition -eq "[parameters('useExisting')]" }) | Select-Object -First 1
$postgresFirewallRules = @($resources | Where-Object { $_.type -eq 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules' })
$azureServicesRule = $postgresFirewallRules | Select-Object -First 1
$postgresDiagnostic = @($resources | Where-Object { $_.type -eq 'Microsoft.Insights/diagnosticSettings' -and $_.name -eq 'scentiq-postgres-diagnostics' }) | Select-Object -First 1
$postgresLock = @($resources | Where-Object { $_.type -eq 'Microsoft.Authorization/locks' -and $_.name -eq 'scentiq-postgres-protection' }) | Select-Object -First 1

Assert-True ($null -ne $postgresDeployment -and $postgresDeployment.properties.parameters.serverName.value -eq "[parameters('postgresServerName')]") 'the PostgreSQL module must receive the exact adopted server name'
Assert-True ($null -ne $postgresDeployment -and $postgresDeployment.properties.parameters.location.value -eq "[parameters('postgresLocation')]") 'the PostgreSQL module must receive the exact adopted server location'
Assert-True ($postgresServers.Count -eq 2 -and $null -ne $freshPostgresServer -and $null -ne $adoptedPostgresServer) 'PostgreSQL must model distinct fresh-create and adopted in-place parent paths'
foreach ($postgresServer in @($freshPostgresServer, $adoptedPostgresServer)) {
    Assert-True ($null -ne $postgresServer -and $postgresServer.name -eq "[parameters('serverName')]") 'PostgreSQL must retain the exact server resource path'
    Assert-PreservationBaseline $postgresServer @{
        'sku.name' = "[parameters('skuName')]"
        'sku.tier' = 'Burstable'
        'properties.version' = '18'
        'properties.storage.storageSizeGB' = 32
        'properties.storage.autoGrow' = 'Enabled'
        'properties.backup.backupRetentionDays' = 14
        'properties.backup.geoRedundantBackup' = 'Disabled'
        'properties.network.publicNetworkAccess' = 'Enabled'
        'properties.highAvailability.mode' = 'Disabled'
        'properties.maintenanceWindow.customWindow' = 'Enabled'
        'properties.maintenanceWindow.dayOfWeek' = 0
        'properties.maintenanceWindow.startHour' = 7
        'properties.maintenanceWindow.startMinute' = 0
        'properties.authConfig.activeDirectoryAuth' = 'Enabled'
        'properties.authConfig.passwordAuth' = 'Enabled'
        'properties.authConfig.tenantId' = "[parameters('tenantId')]"
        'properties.dataEncryption.type' = 'SystemManaged'
    } 'the PostgreSQL preservation baseline'
}
Assert-True ($null -ne $adoptedPostgresServer -and -not $adoptedPostgresServer.properties.PSObject.Properties['administratorLogin'] -and -not $adoptedPostgresServer.properties.PSObject.Properties['administratorLoginPassword'] -and -not $adoptedPostgresServer.PSObject.Properties['identity']) 'the adopted PostgreSQL path must not update administrator credentials or identity'
Assert-PreservationBaseline $adoptedPostgresServer @{
    'properties.storage.iops' = 120
    'properties.storage.tier' = 'P4'
    'properties.storage.type' = 'Premium_LRS'
    'properties.replica.role' = 'Primary'
    'properties.replicationRole' = 'Primary'
} 'the adopted PostgreSQL preservation baseline'

$expectedAdoptedTagExpression = "[union(parameters('existingTags'), parameters('commonTags'))]"
Assert-True ($null -ne $adoptedPostgresServer -and $adoptedPostgresServer.tags -eq $expectedAdoptedTagExpression) 'the adopted PostgreSQL parent PUT must preserve all supplied live tags before applying common tags'
Assert-True ($null -ne $postgresDeployment -and $postgresDeployment.properties.parameters.existingTags.value -eq "[parameters('postgresExistingTags')]") 'the PostgreSQL module must receive the explicit live-tag preservation contract'
Assert-True (@($resources | Where-Object { $_.type -eq 'Microsoft.Resources/tags' -and $_.scope -match 'Microsoft.DBforPostgreSQL/flexibleServers' }).Count -eq 0) 'PostgreSQL tag preservation must be part of the adopted parent PUT, not a post-PUT tag extension'

$postgresDatabases = @($resources | Where-Object { $_.type -eq 'Microsoft.DBforPostgreSQL/flexibleServers/databases' })
$scentiqDatabase = $postgresDatabases | Where-Object { $_.name -eq "[format('{0}/{1}', parameters('serverName'), 'scentiq_dev')]" } | Select-Object -First 1
Assert-True ($postgresDatabases.Count -eq 1 -and $null -ne $scentiqDatabase -and $scentiqDatabase.properties.charset -eq 'UTF8' -and $scentiqDatabase.properties.collation -eq 'en_US.utf8') 'PostgreSQL must manage only the scentiq_dev database with its observed collation'
$tlsConfiguration = @($resources | Where-Object { $_.type -eq 'Microsoft.DBforPostgreSQL/flexibleServers/configurations' -and $_.name -eq "[format('{0}/{1}', parameters('serverName'), 'require_secure_transport')]" }) | Select-Object -First 1
Assert-True ($null -ne $tlsConfiguration -and $tlsConfiguration.properties.value -eq 'on') 'PostgreSQL must require TLS without taking ownership of unrelated server configurations'

$allowAzureServicesRuleExpression = "[and(equals(parameters('deploymentMode'), 'dev'), equals(parameters('networkMode'), 'publicDev'))]"
Assert-True ($null -ne $azureServicesRule -and $azureServicesRule.name -eq "[format('{0}/{1}', parameters('serverName'), parameters('azureServicesFirewallRuleName'))]" -and $azureServicesRule.condition -eq "[parameters('allowAzureServicesFirewallRule')]") 'PostgreSQL must retain the exact conditional Azure-services firewall rule path'
Assert-True ($null -ne $postgresDeployment -and $postgresDeployment.properties.parameters.allowAzureServicesFirewallRule.value -eq $allowAzureServicesRuleExpression) 'the PostgreSQL module must derive Azure-services firewall access only from the deployment and network modes'
Assert-True (@($postgresFirewallRules | Where-Object { $_.properties.startIpAddress -eq '0.0.0.0' -and $_.properties.endIpAddress -eq '255.255.255.255' }).Count -eq 0) 'PostgreSQL must not declare an unrestricted IPv4 firewall rule'
Assert-True ($null -ne $postgresDiagnostic -and $postgresDiagnostic.scope -eq "[resourceId('Microsoft.DBforPostgreSQL/flexibleServers', parameters('serverName'))]" -and $postgresDiagnostic.properties.logs[0].categoryGroup -eq 'allLogs' -and $postgresDiagnostic.properties.metrics[0].category -eq 'AllMetrics') 'PostgreSQL diagnostics must target the exact server with all logs and metrics'
Assert-True ($null -ne $postgresLock -and $postgresLock.scope -eq "[resourceId('Microsoft.DBforPostgreSQL/flexibleServers', parameters('serverName'))]" -and $postgresLock.properties.level -eq 'CanNotDelete' -and $postgresLock.condition -eq "[parameters('enablePostgresLock')]") 'PostgreSQL must model a staged CanNotDelete lock on the exact server'

if ($Mode -eq 'dev') {
    Assert-True ($null -ne $deploymentParameters -and $deploymentParameters.deploymentMode.value -eq 'dev') 'dev verifier runs must receive compiled development parameters'
    Assert-True ($null -ne $deploymentParameters -and $deploymentParameters.postgresServerName.value -eq 'scentiq-pg-dev-eus') 'development parameters must bind the exact adopted PostgreSQL server name'
    Assert-True ($null -ne $deploymentParameters -and $deploymentParameters.postgresAzureServicesFirewallRuleName.value -eq 'AllowAllAzureServicesAndResourcesWithinAzureIps_2026-8-6_22-2-8') 'development parameters must bind the exact adopted Azure-services firewall rule name'
    Assert-True ($null -ne $deploymentParameters -and $deploymentParameters.postgresExistingTags.value -is [object]) 'development parameters must supply the complete redacted PostgreSQL live-tag preservation contract'
    Assert-True ($null -ne $deploymentParameters -and $deploymentParameters.useExistingFoundation.value -eq $true -and $azureServicesRule.properties.startIpAddress -eq '0.0.0.0' -and $azureServicesRule.properties.endIpAddress -eq '0.0.0.0') 'development adoption must retain only the exact Azure-services firewall rule'
}
else {
    Assert-True ($null -ne $deploymentParameters) "$Mode verifier runs must receive compiled $Mode parameters; do not reuse development parameters"
    Assert-True ($null -ne $deploymentParameters -and $deploymentParameters.deploymentMode.value -eq $Mode) "$Mode parameters must declare deploymentMode '$Mode'"
    Assert-True ($null -ne $deploymentParameters -and $deploymentParameters.networkMode.value -ne 'publicDev') "$Mode parameters must not enable public development networking"
    Assert-True ($null -ne $deploymentParameters -and $deploymentParameters.postgresAzureServicesFirewallRuleName.value -is [string] -and $deploymentParameters.postgresAzureServicesFirewallRuleName.value.Length -gt 0) "$Mode parameters must supply an explicit deterministic PostgreSQL firewall rule name"
}

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    exit 1
}
