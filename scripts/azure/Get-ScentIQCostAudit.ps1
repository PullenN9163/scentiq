param(
    [string]$ResourceGroup = 'scentiq-rg-dev-eus',
    [string]$OutputPath = (Join-Path (Split-Path $PSScriptRoot -Parent) '..\..\artifacts\azure-cost-audit.json'),
    [int]$MaxRetries = 5
)
$ErrorActionPreference = 'Stop'
if ($MaxRetries -lt 0 -or $MaxRetries -gt 8) { throw 'MaxRetries must be between 0 and 8.' }
$subscriptionId = (az account show --query id --output tsv).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($subscriptionId)) { throw 'Azure CLI must have an active subscription.' }
$accessToken = (az account get-access-token --resource https://management.azure.com/ --query accessToken --output tsv).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($accessToken)) { throw 'Could not acquire an ARM token through Azure CLI.' }
$scope = "/subscriptions/$subscriptionId/resourceGroups/$ResourceGroup"
$uri = "https://management.azure.com${scope}/providers/Microsoft.CostManagement/query?api-version=2023-03-01"
$body = @{
    type = 'ActualCost'
    timeframe = 'MonthToDate'
    dataset = @{
        granularity = 'None'
        aggregation = @{ totalCost = @{ name = 'PreTaxCost'; function = 'Sum' } }
        grouping = @(@{ type = 'Dimension'; name = 'MeterCategory' })
    }
} | ConvertTo-Json -Depth 10 -Compress
$headers = @{ Authorization = "Bearer $accessToken" }
$accessToken = $null
$result = $null
for ($attempt = 0; $attempt -le $MaxRetries; $attempt++) {
    try {
        $result = Invoke-RestMethod -Method Post -Uri $uri -Headers $headers -ContentType 'application/json' -Body $body
        break
    } catch {
        $status = [int]$_.Exception.Response.StatusCode
        if ($status -ne 429 -or $attempt -ge $MaxRetries) { throw }
        $retryAfter = 2
        try { $retryAfter = [int]$_.Exception.Response.Headers.RetryAfter.Delta.TotalSeconds } catch { }
        if ($retryAfter -lt 1) { $retryAfter = [Math]::Min(2 * [Math]::Pow(2, $attempt), 30) }
        Start-Sleep -Seconds ([Math]::Min($retryAfter, 60))
    }
}
$outputDirectory = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
$audit = [ordered]@{
    queriedAtUtc = [DateTime]::UtcNow.ToString('o')
    scope = $scope
    currency = 'USD (confirm returned currency in rows)'
    timeframe = 'MonthToDate ActualCost, pre-tax'
    result = $result
}
$audit | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $OutputPath -Encoding utf8
Write-Output "Private cost audit written to $OutputPath"
