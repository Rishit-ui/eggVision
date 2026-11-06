[CmdletBinding()]
param(
    [switch]$SkipFrontend,
    [switch]$SkipDocker
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$runId = Get-Date -Format 'yyyyMMdd-HHmmss'
$artifactRoot = Join-Path $repositoryRoot "artifacts\verification\$runId"
New-Item -ItemType Directory -Path $artifactRoot -Force | Out-Null

$python = Join-Path $repositoryRoot 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "Required backend virtual environment not found: $python"
}

$env:PYTHONPATH = "$repositoryRoot;$repositoryRoot\backend"
$results = [System.Collections.Generic.List[object]]::new()

function Invoke-VerificationCheck {
    param(
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [string]$Executable,
        [string[]]$Arguments = @(),
        [string]$WorkingDirectory = $repositoryRoot,
        [bool]$Required = $true
    )

    $logPath = Join-Path $artifactRoot ("{0}.log" -f $Name)
    $started = Get-Date
    Push-Location $WorkingDirectory
    $prevEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $Executable @Arguments *> $logPath
        $exitCode = if ($LASTEXITCODE -ne $null) { $LASTEXITCODE } else { 0 }
    }
    catch {
        $_ | Out-File -LiteralPath $logPath -Append -Encoding utf8
        $exitCode = 1
    }
    finally {
        $ErrorActionPreference = $prevEAP
        Pop-Location
    }
    $duration = [Math]::Round(((Get-Date) - $started).TotalSeconds, 2)
    $status = if ($exitCode -eq 0) { 'PASS' } else { 'FAIL' }
    $results.Add([PSCustomObject]@{
        name = $Name; status = $status; required = $Required; exit_code = $exitCode
        duration_seconds = $duration; log = $logPath
    })
    Write-Host ("[{0}] {1} ({2}s)" -f $status, $Name, $duration)
    return $exitCode
}

function Add-NotApplicableCheck {
    param([string]$Name, [string]$Reason)
    $results.Add([PSCustomObject]@{
        name = $Name; status = 'NOT_APPLICABLE'; required = $false; exit_code = $null
        duration_seconds = 0; log = $Reason
    })
    Write-Host ("[NOT APPLICABLE] {0}: {1}" -f $Name, $Reason)
}

Set-Location $repositoryRoot
$metadata = @{
    generated_at = (Get-Date).ToString('o')
    repository_root = $repositoryRoot
    git_head = (& git rev-parse HEAD)
    git_branch = (& git branch --show-current)
    git_status = (& git status --short --branch)
    python = (& $python --version)
    node = (& node --version 2>$null)
    npm = (& npm --version 2>$null)
    os = [System.Environment]::OSVersion.VersionString
}
$metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $artifactRoot 'environment.json') -Encoding utf8

$manifestScript = Join-Path $repositoryRoot 'scripts\protected_data_manifest.py'
$beforeManifest = Join-Path $artifactRoot 'protected-data-before.json'
$afterManifest = Join-Path $artifactRoot 'protected-data-after.json'
Invoke-VerificationCheck -Name 'protected-data-before' -Executable $python -Arguments @($manifestScript, '--output', $beforeManifest) | Out-Null
Invoke-VerificationCheck -Name 'pip-check' -Executable $python -Arguments @('-m', 'pip', 'check') | Out-Null
Invoke-VerificationCheck -Name 'ruff' -Executable $python -Arguments @('-m', 'ruff', 'check', 'backend', 'ml', 'scripts', 'tests') | Out-Null
Invoke-VerificationCheck -Name 'pytest-coverage' -Executable $python -Arguments @('-m', 'coverage', 'run', '--source=backend,ml,scripts', '-m', 'pytest', 'tests', 'ml/tests', '-q', "--junitxml=$artifactRoot\pytest.xml") | Out-Null
Invoke-VerificationCheck -Name 'coverage-xml' -Executable $python -Arguments @('-m', 'coverage', 'xml', '-o', "$artifactRoot\coverage.xml") | Out-Null
Invoke-VerificationCheck -Name 'coverage-html' -Executable $python -Arguments @('-m', 'coverage', 'html', '-d', "$artifactRoot\htmlcov") | Out-Null
Invoke-VerificationCheck -Name 'openapi-generation' -Executable $python -Arguments @('-c', "import json; from app.main import app; from pathlib import Path; Path(r'$artifactRoot\openapi.json').write_text(json.dumps(app.openapi(), indent=2), encoding='utf-8')") | Out-Null

if ($SkipFrontend) {
    Add-NotApplicableCheck -Name 'frontend' -Reason 'Skipped by -SkipFrontend.'
}
else {
    $frontendDirectory = Join-Path $repositoryRoot 'frontend'
    if (-not (Test-Path -LiteralPath (Join-Path $frontendDirectory 'node_modules'))) {
        Invoke-VerificationCheck -Name 'frontend-npm-ci' -Executable 'npm' -Arguments @('ci') -WorkingDirectory $frontendDirectory | Out-Null
    }
    else {
        Add-NotApplicableCheck -Name 'frontend-npm-ci' -Reason 'Existing node_modules used; run npm ci separately to reinstall from lockfile.'
    }
    Invoke-VerificationCheck -Name 'frontend-lint' -Executable 'npm' -Arguments @('run', 'lint') -WorkingDirectory $frontendDirectory | Out-Null
    Invoke-VerificationCheck -Name 'frontend-type-check' -Executable 'npm' -Arguments @('run', 'type-check') -WorkingDirectory $frontendDirectory | Out-Null
    # Ensure .next directory is clean and writable
    $nextDir = Join-Path $frontendDirectory '.next'
    if (Test-Path -LiteralPath $nextDir) {
        Remove-Item -Recurse -Force -LiteralPath $nextDir
    }
    New-Item -ItemType Directory -Path (Join-Path $frontendDirectory '.next\types\app'), (Join-Path $frontendDirectory '.next\static\chunks\app') -Force | Out-Null
    Invoke-VerificationCheck -Name 'frontend-build' -Executable 'npm' -Arguments @('run', 'build') -WorkingDirectory $frontendDirectory | Out-Null
    Add-NotApplicableCheck -Name 'frontend-unit-tests' -Reason 'No frontend test script is configured in frontend/package.json.'
}

if ($SkipDocker) {
    Add-NotApplicableCheck -Name 'docker' -Reason 'Skipped by -SkipDocker.'
}
else {
    & docker info *> (Join-Path $artifactRoot 'docker-info.log')
    if ($LASTEXITCODE -eq 0) {
        Invoke-VerificationCheck -Name 'docker-compose-config' -Executable 'docker' -Arguments @('compose', 'config', '--no-interpolate') | Out-Null
        Invoke-VerificationCheck -Name 'docker-backend-build' -Executable 'docker' -Arguments @('build', '-f', 'docker/backend.Dockerfile', '-t', 'eggvision-backend-verify', '.') | Out-Null
        Invoke-VerificationCheck -Name 'docker-frontend-build' -Executable 'docker' -Arguments @('build', '-f', 'docker/frontend.Dockerfile', '-t', 'eggvision-frontend-verify', './frontend') | Out-Null
    }
    else {
        Add-NotApplicableCheck -Name 'docker-compose-config' -Reason 'Docker daemon unavailable; see docker-info.log.'
        Add-NotApplicableCheck -Name 'docker-image-builds' -Reason 'Docker daemon unavailable; see docker-info.log.'
    }
}

Invoke-VerificationCheck -Name 'protected-data-after' -Executable $python -Arguments @($manifestScript, '--output', $afterManifest, '--compare', $beforeManifest) | Out-Null

$summary = [PSCustomObject]@{
    run_id = $runId
    generated_at = (Get-Date).ToString('o')
    overall_status = if (@($results | Where-Object { $_.required -and $_.status -eq 'FAIL' }).Count -eq 0) { 'PASS' } else { 'FAIL' }
    results = $results
}
$summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $artifactRoot 'summary.json') -Encoding utf8
$summary.results | Format-Table -AutoSize | Out-String | Set-Content -LiteralPath (Join-Path $artifactRoot 'summary.txt') -Encoding utf8

if ($summary.overall_status -ne 'PASS') {
    exit 1
}
