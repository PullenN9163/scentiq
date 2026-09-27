param(
    [Parameter(Mandatory)] [string] $RepositoryRoot,
    [Parameter(Mandatory)] [ValidateSet('tracked', 'staged')] [string] $Scope
)

$repositoryPath = (Resolve-Path -LiteralPath $RepositoryRoot -ErrorAction Stop).Path
$failures = [System.Collections.Generic.List[string]]::new()
$forbiddenPathPattern = '(^|/)(\.ai|\.codex|\.openai|\.chatgpt|\.superpowers)(/|$)|codex|chatgpt|claude|conversation|transcript|prompt|ai[-_ ]?(draft|plan)'
$forbiddenContentPattern = '(?im)^(user|assistant|system):\s|^(prompt|conversation transcript):\s|generated (by|with) (chatgpt|codex|claude)|ai[- ]generated (draft|plan)'

$pathArguments = if ($Scope -eq 'staged') {
    @('diff', '--cached', '--name-only', '--diff-filter=ACMR')
}
else {
    @('ls-files')
}

$paths = @(& git -C $repositoryPath $pathArguments 2>$null)
if ($LASTEXITCODE -ne 0) {
    Write-Error "Unable to list $Scope paths for repository privacy verification."
    exit 1
}

foreach ($path in $paths) {
    if ([string]::IsNullOrWhiteSpace($path)) {
        continue
    }

    $normalizedPath = $path.Replace('\', '/')
    if ($normalizedPath -match $forbiddenPathPattern) {
        $failures.Add("forbidden path: $normalizedPath")
        continue
    }

    $content = & git -C $repositoryPath show ":$path" 2>$null
    if ($LASTEXITCODE -ne 0) {
        $failures.Add("unable to inspect content: $normalizedPath")
        continue
    }

    if (($content -join [Environment]::NewLine) -match $forbiddenContentPattern) {
        $failures.Add("forbidden content marker: $normalizedPath")
    }
}

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    exit 1
}
