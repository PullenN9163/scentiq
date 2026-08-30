[CmdletBinding()]
param(
    [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string] $ResourceGroupName,
    [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string] $ServerName,
    [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string] $RestoreServerName,
    [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string] $RestorePoint,
    [Parameter(Mandatory)] [ValidateNotNullOrEmpty()] [string] $ExpectedDatabaseName,
    [string] $TargetResourceGroupName = 'scentiq-rg-test-eus',
    [switch] $PreflightOnly,
    [switch] $CleanupOnly,
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

if ($ResourceGroupName -eq $TargetResourceGroupName -and $ServerName -eq $RestoreServerName) {
    Write-Error 'Source and target identify the same resource; a restore target must be distinct from its source.'
    exit 1
}

if ($PreflightOnly -and ($CleanupOnly -or $DeleteAfterVerification)) {
    Write-Error 'PreflightOnly cannot be combined with cleanup or deletion switches.'
    exit 1
}

if ($CleanupOnly -and -not $DeleteAfterVerification) {
    Write-Error 'CleanupOnly requires the explicit DeleteAfterVerification confirmation switch.'
    exit 1
}

if ($DeleteAfterVerification -and -not $CleanupOnly) {
    Write-Error 'DeleteAfterVerification requires CleanupOnly so deletion cannot occur in the normal restore path.'
    exit 1
}

$parsedRestorePoint = [DateTimeOffset]::MinValue
if (-not [DateTimeOffset]::TryParse($RestorePoint, [ref] $parsedRestorePoint) -or $parsedRestorePoint.Offset -ne [TimeSpan]::Zero) {
    Write-Error 'RestorePoint must be an ISO 8601 UTC timestamp, for example 2026-08-29T00:00:00Z.'
    exit 1
}

if ($parsedRestorePoint -gt [DateTimeOffset]::UtcNow) {
    Write-Error 'RestorePoint must not be in the future.'
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

function Assert-TargetServerAbsent {
    $result = & az postgres flexible-server show --resource-group $TargetResourceGroupName --name $RestoreServerName --query id --output tsv --only-show-errors 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 0) {
        throw "Restore target '$RestoreServerName' already exists in '$TargetResourceGroupName'. Use a new approved restore name; do not overwrite an existing server."
    }

    if (($result | Out-String) -match 'ResourceNotFound|was not found|could not be found') {
        return
    }

    throw "Unable to confirm that restore target '$RestoreServerName' is absent. Azure CLI exit code: $exitCode"
}

function Assert-RestoreTargetReadyAndContainsExpectedDatabase {
    $state = (Invoke-AzCli @('postgres', 'flexible-server', 'show', '--resource-group', $TargetResourceGroupName, '--name', $RestoreServerName, '--query', 'state', '--output', 'tsv')).Trim()
    if ($state -ne 'Ready') {
        throw "Restore target '$RestoreServerName' is not Ready; refusing cleanup. Current state: $state"
    }

    $databaseNames = @(Invoke-AzCli @('postgres', 'flexible-server', 'db', 'list', '--resource-group', $TargetResourceGroupName, '--server-name', $RestoreServerName, '--query', '[].name', '--output', 'tsv'))
    if ($databaseNames -notcontains $ExpectedDatabaseName) {
        throw "Restore target '$RestoreServerName' does not contain the expected database '$ExpectedDatabaseName'; refusing cleanup."
    }
}

try {
    if ($CleanupOnly) {
        Assert-RestoreTargetReadyAndContainsExpectedDatabase
        Invoke-AzCli @('postgres', 'flexible-server', 'delete', '--resource-group', $TargetResourceGroupName, '--name', $RestoreServerName, '--yes', '--only-show-errors') | Out-Null
        Write-Output "Deleted validated restore target '$RestoreServerName' from '$TargetResourceGroupName'."
        return
    }

    $sourceMetadata = (Invoke-AzCli @('postgres', 'flexible-server', 'show', '--resource-group', $ResourceGroupName, '--name', $ServerName, '--query', '{id:id,state:state,earliestRestoreDate:backup.earliestRestoreDate}', '--output', 'json') | Out-String | ConvertFrom-Json)
    $sourceServerId = [string] $sourceMetadata.id
    if ($sourceMetadata.state -ne 'Ready') {
        throw "Source server '$ServerName' is not Ready; refusing restore. Current state: $($sourceMetadata.state)"
    }

    $earliestRestoreDate = [DateTimeOffset]::MinValue
    if ([string]::IsNullOrWhiteSpace([string] $sourceMetadata.earliestRestoreDate) -or -not [DateTimeOffset]::TryParse([string] $sourceMetadata.earliestRestoreDate, [ref] $earliestRestoreDate)) {
        throw "Source server '$ServerName' did not return backup.earliestRestoreDate; refusing restore."
    }

    if ($parsedRestorePoint -lt $earliestRestoreDate.ToUniversalTime()) {
        throw "RestorePoint is earlier than the source server backup.earliestRestoreDate ($($earliestRestoreDate.ToUniversalTime().ToString('o')))."
    }

    $sourceResourceGroupId = (Invoke-AzCli @('group', 'show', '--name', $ResourceGroupName, '--query', 'id', '--output', 'tsv')).Trim()
    $targetResourceGroupId = (Invoke-AzCli @('group', 'show', '--name', $TargetResourceGroupName, '--query', 'id', '--output', 'tsv')).Trim()

    if ([string]::IsNullOrWhiteSpace($sourceServerId) -or [string]::IsNullOrWhiteSpace($sourceResourceGroupId) -or [string]::IsNullOrWhiteSpace($targetResourceGroupId)) {
        throw 'Unable to resolve the required source server or resource group identifiers.'
    }

    Write-Output "Source server ID: $sourceServerId"
    Write-Output "Source resource group ID: $sourceResourceGroupId"
    Write-Output "Target resource group ID: $targetResourceGroupId"
    Write-Output "Source earliest restore date: $($earliestRestoreDate.ToUniversalTime().ToString('o'))"

    Assert-TargetServerAbsent

    if ($PreflightOnly) {
        Write-Output "Preflight succeeded: source is Ready, restore point is within retention, and target '$RestoreServerName' is absent. No restore was started."
        return
    }

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

    Assert-RestoreTargetReadyAndContainsExpectedDatabase

    Write-Output "Restore verification succeeded: server is Ready and database '$ExpectedDatabaseName' exists."
    $cleanupCommand = ".\scripts\azure\Test-PostgresRestore.ps1 -ResourceGroupName '$ResourceGroupName' -ServerName '$ServerName' -RestoreServerName '$RestoreServerName' -RestorePoint '$RestorePoint' -ExpectedDatabaseName '$ExpectedDatabaseName' -TargetResourceGroupName '$TargetResourceGroupName' -CleanupOnly -DeleteAfterVerification"
    Write-Output "To delete this validated restore target, run exactly: $cleanupCommand"
}
catch {
    Write-Error $_
    exit 1
}
