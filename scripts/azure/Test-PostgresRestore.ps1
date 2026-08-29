[CmdletBinding()]
param(
    [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string] $ResourceGroupName,
    [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string] $ServerName,
    [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string] $RestoreServerName,
    [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string] $RestorePoint,
    [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string] $ExpectedDatabaseName,
    [string] $TargetResourceGroupName = 'scentiq-rg-test-eus',
    [switch] $DeleteAfterVerification
)

$approvedRestoreNamePrefix = 'scentiq-pg-restore-'
$approvedTargetResourceGroup = 'scentiq-rg-test-eus'

if (-not $RestoreServerName.StartsWith($approvedRestoreNamePrefix, [System.StringComparison]::Ordinal)) {
    Write-Error "RestoreServerName must start with '$approvedRestoreNamePrefix'."
    exit 1
}

if ($TargetResourceGroupName -ne $approvedTargetResourceGroup) {
    Write-Error "TargetResourceGroupName must be the explicit test resource group '$approvedTargetResourceGroup'."
    exit 1
}

$parsedRestorePoint = [DateTimeOffset]::MinValue
if (-not [DateTimeOffset]::TryParse($RestorePoint, [ref] $parsedRestorePoint) -or $parsedRestorePoint.Offset -ne [TimeSpan]::Zero) {
    Write-Error 'RestorePoint must be an ISO 8601 UTC timestamp, for example 2026-08-29T00:00:00Z.'
    exit 1
}

function Invoke-AzCli {
    param([Parameter(Mandatory)] [string[]] $Arguments)

    $result = & az @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI command failed: az $($Arguments -join ' ')"
    }

    return $result
}

try {
    $sourceServerId = (Invoke-AzCli @('postgres', 'flexible-server', 'show', '--resource-group', $ResourceGroupName, '--name', $ServerName, '--query', 'id', '--output', 'tsv')).Trim()
    $sourceResourceGroupId = (Invoke-AzCli @('group', 'show', '--name', $ResourceGroupName, '--query', 'id', '--output', 'tsv')).Trim()
    $targetResourceGroupId = (Invoke-AzCli @('group', 'show', '--name', $TargetResourceGroupName, '--query', 'id', '--output', 'tsv')).Trim()

    if ([string]::IsNullOrWhiteSpace($sourceServerId) -or [string]::IsNullOrWhiteSpace($sourceResourceGroupId) -or [string]::IsNullOrWhiteSpace($targetResourceGroupId)) {
        throw 'Unable to resolve the required source server or resource group identifiers.'
    }

    Write-Output "Source server ID: $sourceServerId"
    Write-Output "Source resource group ID: $sourceResourceGroupId"
    Write-Output "Target resource group ID: $targetResourceGroupId"

    Invoke-AzCli @('postgres', 'flexible-server', 'restore', '--resource-group', $TargetResourceGroupName, '--name', $RestoreServerName, '--source-server', $sourceServerId, '--restore-time', $RestorePoint, '--yes', '--only-show-errors') | Out-Null

    $deadline = [DateTimeOffset]::UtcNow.AddMinutes(45)
    do {
        $state = (Invoke-AzCli @('postgres', 'flexible-server', 'show', '--resource-group', $TargetResourceGroupName, '--name', $RestoreServerName, '--query', 'state', '--output', 'tsv')).Trim()
        if ($state -eq 'Ready') {
            break
        }

        if ([DateTimeOffset]::UtcNow -ge $deadline) {
            throw "Restored server did not reach Ready before $($deadline.ToString('o')). Last state: $state"
        }

        Start-Sleep -Seconds 15
    } while ($true)

    $databaseNames = @(Invoke-AzCli @('postgres', 'flexible-server', 'db', 'list', '--resource-group', $TargetResourceGroupName, '--server-name', $RestoreServerName, '--query', '[].name', '--output', 'tsv'))
    if ($databaseNames -notcontains $ExpectedDatabaseName) {
        throw "Restored server does not contain the expected database '$ExpectedDatabaseName'."
    }

    Write-Output "Restore verification succeeded: server is Ready and database '$ExpectedDatabaseName' exists."
    $cleanupCommand = ".\scripts\azure\Test-PostgresRestore.ps1 -ResourceGroupName '$ResourceGroupName' -ServerName '$ServerName' -RestoreServerName '$RestoreServerName' -RestorePoint '$RestorePoint' -ExpectedDatabaseName '$ExpectedDatabaseName' -TargetResourceGroupName '$TargetResourceGroupName' -DeleteAfterVerification"
    Write-Output "To delete this restore target after review, run exactly: $cleanupCommand"

    if ($DeleteAfterVerification) {
        Invoke-AzCli @('postgres', 'flexible-server', 'delete', '--resource-group', $TargetResourceGroupName, '--name', $RestoreServerName, '--yes', '--only-show-errors') | Out-Null
        Write-Output "Deleted restore target '$RestoreServerName' from '$TargetResourceGroupName'."
    }
}
catch {
    Write-Error $_
    exit 1
}
