param(
    [Parameter(Mandatory)] [string] $TemplatePath,
    [Parameter(Mandatory)] [ValidateSet('dev', 'test', 'prod-reference')] [string] $Mode
)

$template = Get-Content -Raw -LiteralPath $TemplatePath | ConvertFrom-Json -Depth 100
$failures = [System.Collections.Generic.List[string]]::new()

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
        if ($resource.properties.template.resources) {
            Get-ArmResources $resource.properties.template.resources
        }
    }
}

$resources = @(Get-ArmResources $template.resources)
Assert-True ($resources.Count -gt 0) 'compiled template contains no resources'
Assert-True (-not ($template | ConvertTo-Json -Depth 100 | Select-String -Quiet 'latest')) 'mutable latest image tag is forbidden'
Assert-True (-not ($template | ConvertTo-Json -Depth 100 | Select-String -Quiet '0\.0\.0\.0/0')) 'unrestricted CIDR is forbidden'

if ($Mode -eq 'dev') {
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
