param([string]$RunPrefix = 'formal_main_v1', [string]$Checkpoint = 'resume_split_v2/best_policy.pth')
$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectPath
$stampName = Get-Date -Format 'yyyyMMdd_HHmmss'
$nativePython = if ($env:YOPO_ISAAC_PYTHON) { $env:YOPO_ISAAC_PYTHON } else { 'python' }
if (-not (Get-Command $nativePython -ErrorAction SilentlyContinue)) { throw "Python interpreter not found: '$nativePython'. Set YOPO_ISAAC_PYTHON to the Isaac Sim python.exe (or put python on PATH)." }
$env:OMNI_KIT_ACCEPT_EULA = 'YES' # Same accepted project runtime setting as collection/showcase.
$plantRun = 'physx_unified_' + $stampName
& $nativePython scripts/probe_highspeed_physics.py --run $plantRun *> ('artifacts/formal_training/' + $plantRun + '.log')
$plantResult = Join-Path $projectPath ('artifacts/control_validation/' + $plantRun + '/result.json')
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $plantResult) -or ((Get-Content -LiteralPath $plantResult -Raw | ConvertFrom-Json).status -ne 'passed')) {
    Write-Warning "PhysX plant failed: artifacts/control_validation/$plantRun. Keep diagnostics; training remains independent."
    return
}
$flightRun = 'ros2_scratch_checkpoint_' + $stampName
& $nativePython scripts/run_ros2_navigation.py --run $flightRun --checkpoint $Checkpoint --duration 20 --speed 2 --scope intermediate_scratch_checkpoint_interface_not_final_benchmark *> ('artifacts/formal_training/' + $flightRun + '.log')
if ($LASTEXITCODE -ne 0) {
    Write-Warning "ROS2 smoke flight interface failed: artifacts/ros2_flights/$flightRun. Training remains independent."
}
Write-Output "Native preflights finished; formal training can now use the GPU. Plant=$plantRun Flight=$flightRun"
