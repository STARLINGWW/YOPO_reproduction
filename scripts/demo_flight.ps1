param(
    [ValidateSet('seed0','seed1','seed2','dagger','official')]
    [string]$Model = 'seed0',
    [ValidateSet('ros2','native')]
    [string]$Mode = 'ros2',
    [double]$Speed = 2.0,
    [double]$Duration = 120.0,
    [int]$MapSeed = 3000,
    [ValidateSet('forest','grid')]
    [string]$Scene = 'forest',
    [string]$RunName = '',
    [string]$PythonPath = 'D:\_AAA_FILE_ALL\Anaconda_file\Anaconda_env\isaac61\python.exe',
    [switch]$RenderOnly,
    [switch]$DryRun,
    [switch]$OpenVideo
)
# A new non-matrix flight plus replay. Frozen runtime and benchmark slots are
# untouched. Native demos use a different vehicle and are separate comparisons.
$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectPath
if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) { throw "Python not found: $PythonPath" }
if ($Speed -le 0 -or $Duration -le 0) { throw 'Speed and Duration must be positive' }
if ($RenderOnly -and -not $RunName) { throw 'RenderOnly requires an existing RunName' }
if (-not $RunName) {
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
    $suffix = [guid]::NewGuid().ToString('N').Substring(0,6)
    $RunName = 'view_' + $Mode + '_' + $Model + '_' + $stamp + '_' + $suffix
}
if ($RunName -notmatch '^[A-Za-z0-9_-]+$') { throw 'RunName may contain only letters, digits, underscores and hyphens' }
$checkpointByModel = @{
    seed0 = 'checkpoints/formal_main_v1_seed0/best_policy.pth'
    seed1 = 'checkpoints/formal_main_v1_seed1/best_policy.pth'
    seed2 = 'checkpoints/formal_main_v1_seed2/best_policy.pth'
    dagger = 'checkpoints/dagger_main_v1_seed0/best_policy.pth'
    official = 'external/audit_sources/YOPO-Simple/YOPO/saved/YOPO_1/epoch50.pth'
}
$weightFile = $checkpointByModel[$Model]
$weightSha = $null
if (-not $RenderOnly) {
    if ($Mode -eq 'ros2' -and $Model -in @('dagger','official')) {
        throw 'The frozen ROS2 planner accepts scratch-provenance base runs. Use -Mode native for dagger or official.'
    }
    if (-not (Test-Path -LiteralPath $weightFile -PathType Leaf)) { throw "Checkpoint missing: $weightFile" }
    $weightSha = (Get-FileHash -LiteralPath $weightFile -Algorithm SHA256).Hash.ToLower()
    if ($Model -match '^seed[012]$') {
        $auditFile = Join-Path (Split-Path -Parent $weightFile) 'training_audit.json'
        $audit = Get-Content -LiteralPath $auditFile -Raw -Encoding utf8 | ConvertFrom-Json
        if ($audit.status -ne 'passed' -or $audit.epochs -ne 50 -or $weightSha -ne $audit.selection.best_policy_file_sha256) {
            throw 'The selected base checkpoint is not the audited best policy'
        }
    }
    if ($Model -eq 'dagger') {
        $daggerResult = Get-Content -LiteralPath 'checkpoints/dagger_main_v1_seed0/result.json' -Raw -Encoding utf8 | ConvertFrom-Json
        if ($daggerResult.status -ne 'complete' -or $daggerResult.rehearsal) { throw 'DAgger formal fine-tune is not complete' }
    }
}

$sourceRoot = if ($Mode -eq 'ros2') { 'artifacts/ros2_flights' } else { 'artifacts/navigation' }
$sourceFolder = Join-Path $sourceRoot $RunName
$metricFile = Join-Path $sourceFolder 'metrics.json'
$tag = 'view_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fff')
if ($Mode -eq 'ros2') {
    $flightScript = 'scripts/run_ros2_navigation.py'
    $relativeCheckpoint = $weightFile -replace '^checkpoints/',''
    $flightArgs = @('--run',$RunName,'--checkpoint',$relativeCheckpoint,'--backend','yopo','--device','cuda',
                    '--map-seed',[string]$MapSeed,'--speed',[string]$Speed,'--duration',[string]$Duration,'--scope','weight_flight_demo_not_matrix')
    $renderScript = 'scripts/render_ros2_flight.py'
    $renderArgs = @('--run',$RunName,'--output-tag',$tag)
    $video = Join-Path ('artifacts/ros2_showcase/' + $RunName + '_' + $tag) 'global_trajectory.mp4'
}
else {
    $flightScript = 'scripts/run_navigation.py'
    $planner = if ($Model -eq 'official') { 'simple' } else { 'main' }
    $flightArgs = @('--run',$RunName,'--seed',[string]$MapSeed,'--speed',[string]$Speed,'--duration',[string]$Duration,
                    '--planner',$planner,'--weights',$weightFile,'--scene',$Scene,'--label',('demo ' + $Model + ' in ' + $planner + ' stack'))
    $renderScript = 'scripts/render_flight.py'
    $renderArgs = @('--run',$RunName)
    $video = Join-Path ('artifacts/showcase/' + $RunName) 'yopo_global_flight.mp4'
}
if ($RenderOnly -and -not (Test-Path -LiteralPath $metricFile)) { throw "No flight metrics: $metricFile" }
if (-not $RenderOnly -and (Test-Path -LiteralPath $sourceFolder)) { throw "Run already exists: $sourceFolder" }
$plan = [ordered]@{mode=$Mode; model=$Model; run=$RunName; weight_file=$weightFile; weight_sha256=$weightSha;
    flight_script=$flightScript; flight_arguments=$flightArgs; render_script=$renderScript; render_arguments=$renderArgs;
    metrics=$metricFile; video=$video; render_only=[bool]$RenderOnly; scope='demo outside the frozen benchmark matrix'}
if ($DryRun) { $plan | ConvertTo-Json -Depth 5; return }

$env:OMNI_KIT_ACCEPT_EULA = 'YES'
if (-not $RenderOnly) {
    if ($Mode -eq 'native' -and (Get-Command docker -ErrorAction SilentlyContinue)) {
        $containerNames = @()
        try { $containerNames = @(docker ps --format '{{.Names}}' 2>$null) } catch { $containerNames = @() }
        if ($LASTEXITCODE -eq 0 -and ($containerNames | Where-Object { $_ -match '^yopo-(formal|dagger|flight)' })) {
            throw 'A YOPO GPU job is live; wait for it before starting another demo'
        }
    }
    & $PythonPath $flightScript @flightArgs
    if ($LASTEXITCODE -ne 0) { throw "Flight process failed. Inspect $sourceFolder; no successful result is assumed." }
}
$metrics = Get-Content -LiteralPath $metricFile -Raw -Encoding utf8 | ConvertFrom-Json
if ($metrics.status -notin @('success','timeout','collision','out_of_map')) { throw "No terminal flight evidence: $($metrics.status)" }
$executedSha = if ($Mode -eq 'ros2') { $metrics.checkpoint_sha256 } else { $metrics.weight_sha256 }
if ($weightSha -and $executedSha -ne $weightSha) { throw 'Recorded flight checkpoint hash differs from the selected weights' }
if ($RenderOnly -and $Mode -eq 'native' -and (Test-Path -LiteralPath $video)) {
    Write-Output 'The native replay already exists; opening/referencing the existing video instead of overwriting it.'
}
else {
    & $PythonPath $renderScript @renderArgs
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $video)) { throw "Replay not produced: $video" }
}
$renderManifestFile = Join-Path (Split-Path -Parent $video) 'render_manifest.json'
if (-not (Test-Path -LiteralPath $renderManifestFile)) { throw 'Replay has no completion manifest; a partial MP4 is not accepted' }
$renderManifest = Get-Content -LiteralPath $renderManifestFile -Raw -Encoding utf8 | ConvertFrom-Json
if ($renderManifest.preview_only -or $renderManifest.navigation_status -ne $metrics.status) {
    throw 'Replay manifest is a preview or does not match the flight outcome'
}
$renderSha = if ($Mode -eq 'ros2') { $renderManifest.checkpoint_sha256 } else { $renderManifest.weight_sha256 }
if ($renderSha -and $executedSha -ne $renderSha) { throw 'Replay checkpoint identity differs from the flight metrics' }
$metrics | Select-Object status, path_length_m, goal_error_m, min_net_clearance_m, min_clearance_m, tracking_rmse_m, max_speed_mps
Write-Output ('METRICS: ' + (Join-Path $projectPath $metricFile))
Write-Output ('VIDEO: ' + (Join-Path $projectPath $video))
if ($OpenVideo) { Start-Process -FilePath (Join-Path $projectPath $video) }
