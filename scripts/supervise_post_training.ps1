param(
    [string]$RunPrefix = 'formal_main_v1',
    [int]$PollSeconds = 120,
    [string]$MatrixArguments = '--execute',
    [switch]$SkipMatrix,
    [double]$MaxHours = 96
)
# Wait until the three-seed formal queue is genuinely finished, then run the
# ordered post-training chain:
#   audit,table1,admission -> matrix -> showcase,aggregate,figures,docs,dagger
#   -> acceptance
# The order above is the block order inside run_post_training_pipeline.ps1;
# that script's -Stages argument only selects which stages run.
# Every stage is a separate pwsh invocation with its own log. The GPU stages
# (admission, matrix) re-check for a live trainer themselves, so this supervisor
# can never race the training containers. A missing/failed seed never triggers
# the chain: it only starts once all three result.json files exist and no
# orchestrator or formal container is alive.
$ErrorActionPreference = 'Continue'
$projectPath = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectPath
$logDir = Join-Path $projectPath 'artifacts\environment'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir 'post_training_supervisor.log'
$sentinel = Join-Path $logDir 'post_training_pipeline_launched.json'

function Write-Log([string]$message) {
    Add-Content -LiteralPath $logPath -Value ((Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz') + ' ' + $message)
}

function Invoke-Pipeline([string]$stages, [string]$matrixArgs) {
    $arguments = @('-NoProfile','-ExecutionPolicy','Bypass','-File',
        (Join-Path $PSScriptRoot 'run_post_training_pipeline.ps1'),
        '-RunPrefix',$RunPrefix,'-Stages',$stages)
    if ($matrixArgs) { $arguments += @('-MatrixArguments',$matrixArgs) }
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $stdout = Join-Path $logDir ('post_training_supervisor_' + ($stages -replace ',','_') + '_' + $stamp + '.log')
    $process = Start-Process -FilePath 'pwsh' -ArgumentList $arguments -Wait -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $stdout -RedirectStandardError ($stdout + '.err')
    Write-Log ('PIPELINE stages=' + $stages + ' exit=' + $process.ExitCode + ' log=' + $stdout)
    return $process.ExitCode
}

if (Test-Path -LiteralPath $sentinel) {
    Write-Log ('SUPERVISOR_ALREADY_LAUNCHED sentinel=' + $sentinel)
    exit 0
}

Write-Log ('SUPERVISOR_START poll=' + $PollSeconds + 's prefix=' + $RunPrefix + ' skip_matrix=' + $SkipMatrix + ' pid=' + $PID)
$deadline = (Get-Date).AddHours($MaxHours)
$ready = $false
while (-not $ready) {
    Start-Sleep -Seconds $PollSeconds
    if ((Get-Date) -gt $deadline) { Write-Log 'TIMEOUT_WITHOUT_COMPLETION'; exit 1 }
    $missing = @()
    foreach ($seed in 0,1,2) {
        if (-not (Test-Path -LiteralPath ('checkpoints/' + $RunPrefix + '_seed' + $seed + '/result.json'))) { $missing += $seed }
    }
    if ($missing.Count -gt 0) { continue }
    $orchestrators = @(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq 'pwsh.exe' -and $_.CommandLine -and $_.CommandLine.Contains('run_formal_training.ps1') })
    if ($orchestrators.Count -gt 0) { continue }
    docker version --format '{{.Server.Version}}' *> $null
    if ($LASTEXITCODE -ne 0) { Write-Log 'ENGINE_UNAVAILABLE'; continue }
    $live = docker ps -q --filter 'name=yopo-formal-seed'
    if ($LASTEXITCODE -ne 0) { Write-Log 'DOCKER_PS_FAILED'; continue }
    if ($live) { continue }
    $ready = $true
}
Write-Log 'THREE_SEEDS_PRESENT_AND_GPU_FREE'

$record = [ordered]@{
    started_at = (Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz')
    supervisor_pid = $PID
    run_prefix = $RunPrefix
    stages = @('audit,table1,admission','matrix','aggregate,figures,docs,acceptance')
    matrix_arguments = ($(if ($SkipMatrix) { $null } else { $MatrixArguments }))
    note = 'The matrix stage is allowed to fail without blocking the aggregation stages: coverage gaps and failures stay explicit in the aggregate and the final acceptance audit.'
}
($record | ConvertTo-Json -Depth 4) | Set-Content -LiteralPath $sentinel -Encoding utf8

$admissionExit = Invoke-Pipeline 'audit,table1,admission' $null
if ($admissionExit -ne 0) {
    Write-Log 'ADMISSION_STAGE_FAILED_CHAIN_STOPPED'
    exit 1
}

if (-not $SkipMatrix) {
    # Two batches, same frozen slots: the paper-size first-10 subset (600) runs
    # first so the paper-shaped curves and any harness defect surface early,
    # then the full matrix runs; completed slots are skipped by the driver's
    # own resume logic, and the endpoint remains all 1800 episodes.
    $subsetExit = Invoke-Pipeline 'matrix' ($MatrixArguments + ' --paper-first10')
    Write-Log ('MATRIX_SUBSET_EXIT ' + $subsetExit + ' (600 paper-size slots)')
    $matrixExit = Invoke-Pipeline 'matrix' $MatrixArguments
    Write-Log ('MATRIX_EXIT ' + $matrixExit + ' (full 1800 slots; non-zero is recorded, not hidden; aggregation stages still run)')
}

$finalExit = Invoke-Pipeline 'aggregate,figures,docs,showcase,dagger,acceptance' $null
Write-Log ('CHAIN_FINISHED final_exit=' + $finalExit)
exit $finalExit
