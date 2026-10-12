param(
    [string]$RunPrefix = 'formal_main_v1',
    [string]$DatasetName = 'isaac_full_v1',
    [int]$PollSeconds = 60,
    [string]$PostTrainingStages = 'audit,table1,figures,docs'
)
# Restart the three-seed queue only when it is genuinely absent: the Docker
# engine must be up, no run_formal_training.ps1 orchestrator may be alive, and
# no formal training container may be running. Completed seeds are skipped by
# the queue itself through its own audit, so relaunching never redoes work.
$ErrorActionPreference = 'Continue'
$projectPath = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectPath
$logPath = Join-Path $projectPath 'artifacts\environment\formal_training_supervisor.log'
function Write-Log([string]$message) {
    Add-Content -LiteralPath $logPath -Value ((Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz') + ' ' + $message)
}
Write-Log ('SUPERVISOR_START poll=' + $PollSeconds + 's prefix=' + $RunPrefix)
while ($true) {
    Start-Sleep -Seconds $PollSeconds
    docker version --format '{{.Server.Version}}' *> $null
    if ($LASTEXITCODE -ne 0) { Write-Log 'ENGINE_UNAVAILABLE'; continue }
    $orchestrators = @(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq 'pwsh.exe' -and $_.CommandLine -and $_.CommandLine.Contains('run_formal_training.ps1') })
    if ($orchestrators.Count -gt 0) { continue }
    $live = docker ps -q --filter 'name=yopo-formal-seed'
    if ($LASTEXITCODE -ne 0) { Write-Log 'DOCKER_PS_FAILED'; continue }
    if ($live) { Write-Log ('CONTAINER_WITHOUT_ORCHESTRATOR ' + ($live -join ',')); continue }
    $complete = $true
    foreach ($seed in 0,1,2) {
        if (-not (Test-Path -LiteralPath ('checkpoints/' + $RunPrefix + '_seed' + $seed + '/result.json'))) { $complete = $false }
    }
    if ($complete) {
        Write-Log 'ALL_SEEDS_COMPLETE'
        if ($PostTrainingStages -and $PostTrainingStages -ne 'none') {
            Write-Log ('RUN_POST_TRAINING_STAGES ' + $PostTrainingStages)
            try {
                & (Join-Path $PSScriptRoot 'run_post_training_pipeline.ps1') -RunPrefix $RunPrefix -Stages $PostTrainingStages `
                    *>> (Join-Path $projectPath 'artifacts\environment\formal_training_supervisor_post.log')
                Write-Log ('POST_TRAINING_PIPELINE_EXIT ' + $LASTEXITCODE)
            } catch {
                Write-Log ('POST_TRAINING_PIPELINE_FAILED ' + $_.Exception.Message)
            }
        }
        break
    }
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $stdout = Join-Path $projectPath ('artifacts\environment\formal_training_queue_supervisor_' + $stamp + '.log')
    Write-Log ('RELAUNCHING_QUEUE stdout=' + $stdout)
    Start-Process -FilePath 'pwsh' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',
        (Join-Path $PSScriptRoot 'run_formal_training.ps1'),'-DatasetName',$DatasetName,'-RunPrefix',$RunPrefix) `
        -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError ($stdout + '.err')
    Start-Sleep -Seconds 120
}
