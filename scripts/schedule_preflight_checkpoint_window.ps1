param([string]$ExpectedContainerId, [int]$OrchestratorPid = 86396)
$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectPath
if ($ExpectedContainerId -notmatch '^[a-f0-9]{64}$') { throw 'Require exact verified training container id' }
$runName = 'formal_main_v1_seed0'
$progressPath = Join-Path $projectPath ('checkpoints/' + $runName + '/progress.json')
Write-Output 'Waiting for two complete formal epochs before a checkpointed GPU validation window'
while ($true) {
    $liveId = docker ps -q --no-trunc --filter ('id=' + $ExpectedContainerId)
    if ($LASTEXITCODE -ne 0 -or $liveId -ne $ExpectedContainerId) { throw 'Verified training container is no longer live; inspect without restarting it' }
    $progress = Get-Content -LiteralPath $progressPath -Raw | ConvertFrom-Json
    if ($progress.status -eq 'failed') { throw 'Training failed; inspect trainer evidence' }
    if ($progress.epoch_completed -ge 2) { break }
    Start-Sleep -Seconds 10
}
if ($progress.epoch_completed -ge 50 -or (Test-Path -LiteralPath ('checkpoints/' + $runName + '/result.json'))) { throw 'Training finished; inspect current queue before scheduling GPU work' }
$command = docker inspect $ExpectedContainerId --format '{{json .Config.Cmd}}'
if ($LASTEXITCODE -ne 0 -or -not $command.Contains('train_scratch.py') -or -not $command.Contains($runName)) { throw 'Container identity changed' }
Write-Output "Requesting graceful batch-boundary checkpoint at step $($progress.step)"
docker kill --signal=SIGTERM $ExpectedContainerId
if ($LASTEXITCODE -ne 0) { throw 'Signal request failed; inspect existing container' }
while ($true) {
    $liveId = docker ps -q --no-trunc --filter ('id=' + $ExpectedContainerId)
    if ($LASTEXITCODE -ne 0) { throw 'Unable to verify GPU release' }
    if (-not $liveId) { break }
    Start-Sleep -Seconds 2
}
# The original queue's strict50-epoch audit must fail and stop after this
# intentional early checkpoint. Wait until it has actually exited.
while (Get-Process -Id $OrchestratorPid -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 2 }
$otherGpu = docker ps -q --filter 'name=yopo-formal-seed'
if ($LASTEXITCODE -ne 0 -or $otherGpu) { throw 'Another formal trainer is active; do not overlap GPU work' }
docker compose --profile training run --rm train python3 scripts/audit_resume_readiness.py --run $runName --min-epoch 2 *> artifacts/environment/formal_checkpoint_window.log
if ($LASTEXITCODE -ne 0) { throw 'Checkpoint readiness failed; preserve all state' }
.\scripts\run_isaac_preflights.ps1 -RunPrefix formal_main_v1 -Checkpoint 'formal_main_v1_seed0/policy_epoch_002.pth' *> artifacts/environment/native_preflight_checkpoint_window.log
.\scripts\run_formal_training.ps1 -DatasetName isaac_full_v1 -RunPrefix formal_main_v1 *> artifacts/environment/formal_training_after_preflight.log
