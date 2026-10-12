param(
    [string]$PythonPath = 'D:\_AAA_FILE_ALL\Anaconda_file\Anaconda_env\isaac61\python.exe',
    [string]$RunName = ('showcase_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
)
$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath $PythonPath)) { throw "Python not found: $PythonPath" }
$env:OMNI_KIT_ACCEPT_EULA = 'YES'
$flightLog = Join-Path $projectPath ('artifacts\' + $RunName + '_navigation.log')
& $PythonPath (Join-Path $PSScriptRoot 'run_navigation.py') --run $RunName --seed 7 --speed 1.5 --duration 65 *> $flightLog
$metricFile = Join-Path $projectPath ('artifacts\navigation\' + $RunName + '\metrics.json')
if (-not (Test-Path -LiteralPath $metricFile)) { throw "Navigation produced no metrics. See $flightLog" }
$metrics = Get-Content -LiteralPath $metricFile -Raw | ConvertFrom-Json
if ($metrics.status -ne 'success') { throw "Navigation status: $($metrics.status). See $metricFile" }
$renderLog = Join-Path $projectPath ('artifacts\' + $RunName + '_render.log')
& $PythonPath (Join-Path $PSScriptRoot 'render_flight.py') --run $RunName *> $renderLog
& $PythonPath (Join-Path $PSScriptRoot 'validate_result.py') --run $RunName
if ($LASTEXITCODE -ne 0) { throw 'Artifact validation failed' }
Write-Output (Join-Path $projectPath ('artifacts\showcase\' + $RunName + '\yopo_global_flight.mp4'))
