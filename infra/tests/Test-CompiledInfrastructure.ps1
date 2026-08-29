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
