param(
    [Parameter(Mandatory)] [string] $TemplatePath,
    [Parameter(Mandatory)] [ValidateSet('dev', 'test', 'prod-reference')] [string] $Mode
)

$template = Get-Content -Raw -LiteralPath $TemplatePath | ConvertFrom-Json -Depth 100
$failures = [System.Collections.Generic.List[string]]::new()

function Assert-True([bool] $Condition, [string] $Message) {
    if (-not $Condition) { $script:failures.Add($Message) }
}

function Get-ArmResources([object[]] $Resources) {
    foreach ($resource in $Resources) {
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

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    exit 1
}
