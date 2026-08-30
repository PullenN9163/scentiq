[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $ResourceGroupName,
    [Parameter(Mandatory)] [string] $WorkspaceName,
    [Parameter(Mandatory)] [string] $WebAppName,
    [Parameter(Mandatory)] [string] $ApiAppName,
    [Parameter(Mandatory)] [string] $MigrationJobName,
    [Parameter(Mandatory)] [datetime] $DeploymentStartedAt,
    [datetime] $DeploymentFinishedAt = [datetime]::UtcNow
)

$ErrorActionPreference = 'Stop'
$maxAttempts = 10
$retryIntervalSeconds = 30

if ($DeploymentStartedAt.ToUniversalTime() -gt $DeploymentFinishedAt.ToUniversalTime()) {
    throw 'DeploymentStartedAt must be before DeploymentFinishedAt.'
}

function Get-LogAnalyticsRows([string] $WorkspaceId, [string] $AccessToken, [string] $Query) {
    $headers = @{ Authorization = "Bearer $AccessToken"; 'Content-Type' = 'application/json' }
    $body = @{ query = $Query } | ConvertTo-Json -Compress
    $response = Invoke-RestMethod -Method Post -Uri "https://api.loganalytics.azure.com/v1/workspaces/$WorkspaceId/query" -Headers $headers -Body $body
    if ($null -eq $response.tables -or $response.tables.Count -eq 0) {
        return @()
    }

    $columns = @($response.tables[0].columns | ForEach-Object { $_.name })
    return @($response.tables[0].rows | ForEach-Object {
            $row = [ordered]@{}
            for ($index = 0; $index -lt $columns.Count; $index++) {
                $row[$columns[$index]] = $_[$index]
            }
            [pscustomobject] $row
        })
}

function Get-Count([object[]] $Rows) {
    if ($Rows.Count -eq 0 -or $null -eq $Rows[0].Count) {
        return 0
    }

    return [int] $Rows[0].Count
}

$workspace = az resource show --resource-group $ResourceGroupName --name $WorkspaceName --resource-type 'Microsoft.OperationalInsights/workspaces' --output json | ConvertFrom-Json
if ([string]::IsNullOrWhiteSpace($workspace.customerId)) {
    throw "Log Analytics workspace '$WorkspaceName' did not return a customer ID."
}

# The token is kept only in memory. Do not print command output, headers, or it.
$accessToken = az account get-access-token --resource https://api.loganalytics.io --query accessToken --output tsv
if ([string]::IsNullOrWhiteSpace($accessToken)) {
    throw 'Could not acquire a Log Analytics access token.'
}

$start = $DeploymentStartedAt.ToUniversalTime().ToString('o')
$finish = $DeploymentFinishedAt.ToUniversalTime().ToString('o')
$window = "between (datetime($start) .. datetime($finish))"

$queries = [ordered]@{
    WebRequests = @"
AppRequests
| where TimeGenerated $window
| where AppRoleName has '$WebAppName'
| summarize Count = count()
"@
    CorrelatedApiRequests = @"
let WebOperations = AppRequests
| where TimeGenerated $window
| where AppRoleName has '$WebAppName'
| where isnotempty(OperationId)
| project OperationId;
AppRequests
| where TimeGenerated $window
| where AppRoleName has '$ApiAppName'
| where isnotempty(OperationId)
| where OperationId in (WebOperations)
| summarize Count = count()
"@
    ConsoleRecords = @"
ContainerAppConsoleLogs_CL
| where TimeGenerated $window
| where ContainerAppName_s in ('$WebAppName', '$ApiAppName')
| summarize Count = count() by ContainerAppName_s
"@
    LatestMigration = @"
ContainerAppSystemLogs_CL
| where TimeGenerated $window
| where ContainerAppName_s == '$MigrationJobName'
| top 1 by TimeGenerated desc
| project Status = coalesce(Reason_s, Log_s)
"@
    SensitiveTelemetry = @"
union isfuzzy=true AppRequests, AppDependencies, AppExceptions, AppTraces, ContainerAppConsoleLogs_CL, ContainerAppSystemLogs_CL
| where TimeGenerated $window
| extend Record = tostring(pack_all())
| where Record has 'postgresql+psycopg://' or Record has 'Authorization' or Record has 'Cookie' or Record has 'database-url'
| summarize Count = count()
"@
}

for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
    try {
        $webRequestCount = Get-Count (Get-LogAnalyticsRows -WorkspaceId $workspace.customerId -AccessToken $accessToken -Query $queries.WebRequests)
        $correlatedApiCount = Get-Count (Get-LogAnalyticsRows -WorkspaceId $workspace.customerId -AccessToken $accessToken -Query $queries.CorrelatedApiRequests)
        $consoleRows = Get-LogAnalyticsRows -WorkspaceId $workspace.customerId -AccessToken $accessToken -Query $queries.ConsoleRecords
        $migrationRows = Get-LogAnalyticsRows -WorkspaceId $workspace.customerId -AccessToken $accessToken -Query $queries.LatestMigration
        $sensitiveCount = Get-Count (Get-LogAnalyticsRows -WorkspaceId $workspace.customerId -AccessToken $accessToken -Query $queries.SensitiveTelemetry)

        $consoleApps = @($consoleRows | ForEach-Object { [string] $_.ContainerAppName_s })
        $latestMigrationStatus = if ($migrationRows.Count -gt 0) { [string] $migrationRows[0].Status } else { '' }
        $complete = $webRequestCount -gt 0 -and
            $correlatedApiCount -gt 0 -and
            $consoleApps -contains $WebAppName -and
            $consoleApps -contains $ApiAppName -and
            -not [string]::IsNullOrWhiteSpace($latestMigrationStatus) -and
            $sensitiveCount -eq 0

        if ($complete) {
            [pscustomobject]@{
                attempt = $attempt
                webRequestCount = $webRequestCount
                correlatedApiRequestCount = $correlatedApiCount
                consoleApps = @($consoleApps | Sort-Object -Unique)
                latestMigrationStatus = $latestMigrationStatus.Substring(0, [Math]::Min(120, $latestMigrationStatus.Length))
                sensitiveTelemetryCount = $sensitiveCount
            } | ConvertTo-Json -Compress
            exit 0
        }
    }
    catch {
        # Azure Monitor ingestion can lag; the bounded retry below is intentional.
        if ($attempt -eq $maxAttempts) {
            Write-Error 'Telemetry verification could not query the required sanitized evidence before the retry limit.'
            exit 1
        }
    }

    if ($attempt -lt $maxAttempts) {
        Start-Sleep -Seconds 30
    }
}

Write-Error 'Telemetry has not arrived for all required ScentIQ signals after ten bounded attempts.'
exit 1
