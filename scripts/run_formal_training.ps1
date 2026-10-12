param(
    [string]$DatasetName = 'isaac_full_v1',
    [string]$RunPrefix = 'formal_main_v1',
    [int]$WaitForProducerPid = 0,
    [switch]$PlantPreflight
)
$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectPath
if ($DatasetName -notmatch '^[A-Za-z0-9_-]+$' -or $RunPrefix -notmatch '^[A-Za-z0-9_-]+$') { throw 'Invalid experiment name' }
if ($WaitForProducerPid -gt 0) {
    $producer = Get-CimInstance Win32_Process -Filter "ProcessId=$WaitForProducerPid"
    if ($producer) {
        if (-not $producer.CommandLine.Contains('prepare_dataset.py') -or -not $producer.CommandLine.Contains($DatasetName)) { throw 'Wait target is not the expected data pipeline' }
        Write-Output "Waiting for verified data pipeline PID $WaitForProducerPid"
        Wait-Process -Id $WaitForProducerPid -ErrorAction SilentlyContinue
    }
}
$validationPath = Join-Path $projectPath ('datasets\' + $DatasetName + '\validation.json')
$validation = Get-Content -LiteralPath $validationPath -Raw | ConvertFrom-Json
if ($validation.status -ne 'passed' -or $validation.counts.train -ne 100000 -or $validation.counts.valid -ne 10000 -or $validation.counts.test -ne 10000) { throw 'Full dataset has not passed its required gate' }
$logDir = Join-Path $projectPath 'artifacts\formal_training'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
if ($PlantPreflight) {
    Write-Output 'Data pipeline finished; serial native PhysX and ROS2 preflights'
    & (Join-Path $PSScriptRoot 'run_isaac_preflights.ps1') -RunPrefix $RunPrefix
}
docker compose --profile training run --rm train python3 scripts/stage_training_data.py --name $DatasetName *> (Join-Path $logDir 'stage_data.log')
if ($LASTEXITCODE -ne 0) { throw 'Dataset volume staging failed' }
$archivePath = Join-Path $projectPath ('artifacts\provenance\' + $RunPrefix)
if (-not (Test-Path -LiteralPath $archivePath)) {
    docker compose --profile training run --rm train python3 scripts/archive_reproduction_sources.py --name $RunPrefix *> (Join-Path $logDir 'source_snapshot.log')
    if ($LASTEXITCODE -ne 0) { throw 'Source snapshot failed' }
}
foreach ($seed in 0,1,2) {
    $runName = $RunPrefix + '_seed' + $seed
    $runPath = Join-Path $projectPath ('checkpoints\' + $runName)
    $containerName = 'yopo-formal-seed' + $seed
    $live = docker ps -q --filter ('name=^/' + $containerName + '$')
    if ($live) { throw "Seed already running in $containerName; inspect existing job instead of restarting" }
    if (Test-Path -LiteralPath (Join-Path $runPath 'result.json')) {
        docker compose --profile training run --rm train python3 scripts/audit_training_run.py --run $runName --seed $seed *> (Join-Path $logDir ($runName + '_audit.log'))
        if ($LASTEXITCODE -eq 0) { continue }
    }
    $trainingArgs = @('compose','--profile','training','run','--rm','--name',$containerName,'train','python3','scripts/train_scratch.py','--dataset',('/data/' + $DatasetName),'--run',$runName,'--seed',[string]$seed,'--epochs','50','--batch-size','16')
    if (Test-Path -LiteralPath (Join-Path $runPath 'latest.pt')) { $trainingArgs += '--resume' }
    & docker @trainingArgs *>> (Join-Path $logDir ($runName + '.log'))
    if ($LASTEXITCODE -ne 0) { throw "Training failed for $runName; keep checkpoints and investigate" }
    docker compose --profile training run --rm train python3 scripts/audit_training_run.py --run $runName --seed $seed *>> (Join-Path $logDir ($runName + '_audit.log'))
    if ($LASTEXITCODE -ne 0) { throw "Training audit failed for $runName" }
}
Write-Output 'THREE_SEED_TRAINING_STAGE_FINISHED_NOT_FULL_GOAL_COMPLETION'
