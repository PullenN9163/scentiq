param([Parameter(Mandatory)] [string] $TemplatePath)

$ErrorActionPreference = 'Stop'
$template = Get-Content -Raw -LiteralPath $TemplatePath | ConvertFrom-Json -Depth 100
function Require([bool] $Condition, [string] $Message) {
    if (-not $Condition) { throw $Message }
}
function Resources([object] $Items) {
    $values = if ($Items -is [array]) { $Items } else { @($Items.PSObject.Properties | ForEach-Object Value) }
    foreach ($value in $values) {
        $value
        if ($value.properties.template.resources) { Resources $value.properties.template.resources }
    }
}
$resources = @(Resources $template.resources)
$access = @($resources | Where-Object { $_.type -eq 'Microsoft.Resources/deployments' -and $_.name -match 'agent-access' })
Require ($access.Count -eq 1) 'Exactly one conditional Agent inference integration must exist.'
Require ($access[0].condition -match 'agentEnabled' -and $access[0].condition -match 'foundryAccountName') 'Agent RBAC must be explicitly enabled and bound to an existing account.'
$role = @((Resources $access[0].properties.template.resources) | Where-Object { $_.type -eq 'Microsoft.Authorization/roleAssignments' })
Require ($role.Count -eq 1) 'Agent integration must grant exactly one role.'
Require ($access[0].properties.template.variables.inferenceRoleId -match '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd') 'Agent must use Cognitive Services OpenAI User.'
Require ($role[0].scope -match 'Microsoft.CognitiveServices/accounts' -and $role[0].properties.principalType -eq 'ServicePrincipal') 'Inference role must be account-scoped and assigned to the API identity.'
Require (@($resources | Where-Object { $_.type -like 'Microsoft.CognitiveServices/accounts*' -and $_.existing -ne $true }).Count -eq 0) 'Existing Foundry accounts, projects, and deployments must not be modified.'
$api = @($resources | Where-Object { $_.type -eq 'Microsoft.Resources/deployments' -and $_.name -eq "[format('api-{0}', parameters('environmentName'))]" })[0]
$web = @($resources | Where-Object { $_.type -eq 'Microsoft.Resources/deployments' -and $_.name -eq "[format('web-{0}', parameters('environmentName'))]" })[0]
$apiEnvironment = @($api.properties.parameters.environmentVariables.value)
Require (@($apiEnvironment | Where-Object name -eq 'AZURE_OPENAI_ENDPOINT').Count -eq 1) 'API must receive the inference endpoint.'
Require (@($apiEnvironment | Where-Object name -eq 'AZURE_OPENAI_DEPLOYMENT').Count -eq 1) 'API must receive the deployment name.'
foreach ($surface in @('TODAY', 'WEEK', 'DISCOVERY', 'LAYERING', 'ADVISOR', 'SHADOW')) {
    Require (@($apiEnvironment | Where-Object name -eq "AI_RANKING_${surface}_ENABLED").Count -eq 1) "API must receive the $surface inference flag."
}
Require (@($apiEnvironment | Where-Object name -eq 'AI_MONTHLY_BUDGET_USD').Count -eq 1) 'API must receive the shared inference allowance.'
Require ($template.parameters.aiMonthlyBudgetUsd.maxValue -eq 25) 'Monthly inference allowance must not exceed the approved $25 ceiling.'

$webConfiguration = $web.properties.parameters | ConvertTo-Json -Depth 100
Require ($webConfiguration -notmatch 'AZURE_OPENAI|AGENT_|AI_RANKING|AI_MONTHLY|foundry') 'Provider configuration must stay out of the web workload.'
Require (($template | ConvertTo-Json -Depth 100) -notmatch 'AZURE_OPENAI_API_KEY') 'Azure inference must use managed identity, without an API key secret.'
$inferenceAlerts = @($resources | Where-Object { $_.type -eq 'Microsoft.Insights/scheduledQueryRules' -and $_.name -match 'scentiq-inference' })
Require ($inferenceAlerts.Count -eq 1 -and $inferenceAlerts[0].copy.count -match 'inferenceSignals') 'Inference must monitor fallback, latency, allowance, and planned repeats.'
$inferenceModules = @($resources | Where-Object { $_.type -eq 'Microsoft.Resources/deployments' -and $_.properties.template.variables.inferenceSignals })
Require ($inferenceModules.Count -eq 1 -and $inferenceModules[0].properties.template.variables.inferenceSignals.Count -eq 4) 'Four inference signals must be configured.'
Require ($inferenceAlerts[0].properties.severity -eq 3) 'Inference rollout warnings must use operational severity 3.'
Write-Output 'Agent infrastructure safety checks passed.'
