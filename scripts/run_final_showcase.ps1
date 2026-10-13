param(
    [string]$RunPrefix = 'formal_main_v1',
    [int]$Seed = 0,
    [double]$Speed = 2.0,
    [double]$Duration = 60.0,
    [int]$MapSeed = 3000,
    [string]$Tag = 'final',
    [switch]$RenderOnly,
    [string]$ExistingRun = ''
)
# Final-weight showcase for acceptance item 8: a real closed-loop flight with
# the audited validation-selected checkpoint, then the CPU renderer. The run is
# tagged with a non-primary scope so it can never fill a benchmark slot, and the
# render manifest is extended with the audit hash that selected the checkpoint.
$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectPath
$python = if ($env:YOPO_ISAAC_PYTHON) { $env:YOPO_ISAAC_PYTHON } else { 'python' }
if (-not (Get-Command $python -ErrorAction SilentlyContinue)) { throw "Python interpreter not found: '$python'. Set YOPO_ISAAC_PYTHON to the Isaac Sim python.exe (or put python on PATH)." }
$seedFolder = 'checkpoints/' + $RunPrefix + '_seed' + $Seed
$auditPath = Join-Path $seedFolder 'training_audit.json'
if (-not (Test-Path -LiteralPath $auditPath)) { throw "No training audit for seed $Seed; the final showcase requires a passed 50-epoch audit" }
$audit = Get-Content -LiteralPath $auditPath -Raw | ConvertFrom-Json
if ($audit.status -ne 'passed' -or $audit.epochs -ne 50) { throw "Seed $Seed audit is not a passed 50-epoch audit" }
$checkpoint = Join-Path $seedFolder 'best_policy.pth'
if (-not (Test-Path -LiteralPath $checkpoint)) { throw "Missing audited checkpoint $checkpoint" }
$sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $checkpoint).Hash.ToLower()
if ($sha -ne $audit.selection.best_policy_file_sha256) { throw 'Checkpoint hash does not match the audited validation-selected model' }

function Get-LiveTrainer { docker ps -q --filter 'name=yopo-formal-seed' }

if ($RenderOnly) {
    if (-not $ExistingRun) { throw 'RenderOnly requires -ExistingRun' }
    $runName = $ExistingRun
    $metricsPath = Join-Path (Join-Path 'artifacts/ros2_flights' $runName) 'metrics.json'
    if (-not (Test-Path -LiteralPath $metricsPath)) { throw "No flight metrics for $runName" }
}
else {
    $live = Get-LiveTrainer
    if ($live) { throw 'A formal trainer is live; the final showcase must wait for the GPU' }
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $runName = 'showcase_' + $RunPrefix + '_seed' + $Seed + '_' + $stamp
    $env:OMNI_KIT_ACCEPT_EULA = 'YES'
    & $python scripts/run_ros2_navigation.py --run $runName --checkpoint ($RunPrefix + '_seed' + $Seed + '/best_policy.pth') `
        --device cuda --map-seed $MapSeed --speed $Speed --duration $Duration --scope final_audited_checkpoint_showcase
    if ($LASTEXITCODE -ne 0) { throw "Showcase flight failed; inspect artifacts/ros2_flights/$runName" }
    $metricsPath = Join-Path (Join-Path 'artifacts/ros2_flights' $runName) 'metrics.json'
}
$metrics = Get-Content -LiteralPath $metricsPath -Raw | ConvertFrom-Json
if ($metrics.scope -ne 'final_audited_checkpoint_showcase') { throw "Source run scope is $($metrics.scope); refusing to label it as a final showcase" }
if ($metrics.status -ne 'success') { Write-Warning ("Showcase flight status is " + $metrics.status + "; rendering anyway and NOT claiming success") }

& $python scripts/render_ros2_flight.py --run $runName --output-tag $Tag
if ($LASTEXITCODE -ne 0) { throw 'Render failed' }
$manifestPath = Join-Path ('artifacts/ros2_showcase/' + $runName + '_' + $Tag) 'render_manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$manifest | Add-Member -NotePropertyName audited_best_policy_sha256 -NotePropertyValue $sha -Force
$manifest | Add-Member -NotePropertyName training_audit_sha256 -NotePropertyValue (Get-FileHash -Algorithm SHA256 -LiteralPath $auditPath).Hash.ToLower() -Force
$manifest | Add-Member -NotePropertyName metrics_sha256 -NotePropertyValue (Get-FileHash -Algorithm SHA256 -LiteralPath $metricsPath).Hash.ToLower() -Force
$manifest | Add-Member -NotePropertyName flight_status -NotePropertyValue $metrics.status -Force
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding utf8
Write-Output ('SHOWCASE_DONE run=' + $runName + ' status=' + $metrics.status + ' manifest=' + $manifestPath)
