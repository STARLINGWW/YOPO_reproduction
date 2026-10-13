param(
    [string]$RunPrefix = 'formal_main_v1',
    [string]$Stages = 'audit,table1,figures,docs',
    [string]$MatrixArguments = '',
    [switch]$AllowPartial
)
# Ordered post-training chain. Every stage writes its own log and refuses to
# pretend a missing prerequisite passed. GPU stages run only when no formal
# trainer is live (the native runner enforces this again at start-up).
#
# -Stages only selects WHICH stages run; it does not order them. The execution
# order is the order of the blocks in this file, and that order is deliberate:
#   audit,table1,admission -> matrix -> showcase,aggregate,figures,docs,dagger
#   -> acceptance
# showcase runs before aggregate/figures/docs because the rendered showcase
# artifacts must already exist when the command/evidence audit (docs) walks the
# report paths, and that audit has to pass for the acceptance item that ties a
# showcase run to an audited checkpoint. acceptance is always last.
$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectPath
$logDir = Join-Path $projectPath 'artifacts\environment'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$python = if ($env:YOPO_ISAAC_PYTHON) { $env:YOPO_ISAAC_PYTHON } else { 'python' }
if (-not (Get-Command $python -ErrorAction SilentlyContinue)) { throw "Python interpreter not found: '$python'. Set YOPO_ISAAC_PYTHON to the Isaac Sim python.exe (or put python on PATH)." }
$requested = $Stages.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ }

function Write-Stage([string]$name, [string]$message) {
    Add-Content -LiteralPath (Join-Path $logDir 'post_training_pipeline.log') -Value ((Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz') + " [$name] $message")
}

function Test-SeedAudit([int]$seed, [switch]$Quiet) {
    $run = $RunPrefix + '_seed' + $seed
    $folder = Join-Path $projectPath ('checkpoints\' + $run)
    $auditPath = Join-Path $folder 'training_audit.json'
    $resultPath = Join-Path $folder 'result.json'
    if (-not (Test-Path -LiteralPath $auditPath) -or -not (Test-Path -LiteralPath $resultPath)) {
        if (-not $Quiet) { Write-Stage 'audit' "seed $seed has no completed audit yet ($run)" }
        return $false
    }
    $audit = Get-Content -LiteralPath $auditPath -Raw | ConvertFrom-Json
    $result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
    $ok = ($audit.status -eq 'passed') -and ($audit.epochs -eq 50) -and ($result.status -eq 'complete') -and ($result.steps -eq 312500)
    if (-not $Quiet) { Write-Stage 'audit' "seed $seed audit=$($audit.status) epochs=$($audit.epochs) steps=$($result.steps) ok=$ok" }
    return $ok
}

if ($requested -contains 'audit') {
    Write-Stage 'audit' 'verifying three-seed formal training audits'
    $missing = @()
    foreach ($seed in 0,1,2) { if (-not (Test-SeedAudit $seed)) { $missing += $seed } }
    if ($missing.Count -gt 0) {
        Write-Stage 'audit' ("incomplete seeds: " + ($missing -join ','))
        if (-not $AllowPartial) { throw 'Formal three-seed audits are not complete; post-training pipeline stops here' }
    } else { Write-Stage 'audit' 'all three seed audits passed' }
}

if ($requested -contains 'table1') {
    Write-Stage 'table1' 'rerunning expert comparison with final audited weights'
    foreach ($seed in 0,1,2) {
        $checkpoint = '/workspace/checkpoints/' + $RunPrefix + '_seed' + $seed + '/best_policy.pth'
        $output = '/workspace/artifacts/expert/network_comparison_trained_seed' + $seed + '.json'
        docker compose --profile expert run --rm --name ('yopo-expert-final-seed' + $seed) expert `
            python3 scripts/compare_expert_network.py --checkpoint $checkpoint --label ('trained_seed' + $seed) `
            --output $output --threads 4 *> (Join-Path $logDir ('post_training_table1_seed' + $seed + '.log'))
        if ($LASTEXITCODE -ne 0) { throw ('Expert comparison failed for seed ' + $seed) }
    }
    docker compose --profile expert run --rm --name yopo-expert-final-random expert `
        python3 scripts/compare_expert_network.py --label random_initial --threads 4 *> (Join-Path $logDir 'post_training_table1_random.log')
    if ($LASTEXITCODE -ne 0) { throw 'Expert comparison failed for the random-initial baseline' }
    Write-Stage 'table1' 'expert comparison files written for seeds 0/1/2 and random initial'
}

if ($requested -contains 'admission') {
    $live = docker ps -q --filter 'name=yopo-formal-seed'
    if ($live) { Write-Stage 'admission' 'refused: a formal trainer is live'; throw 'A formal trainer is live; runtime admission must wait for the GPU' }
    $cudaGatePath = 'artifacts/agile_autonomy/torch_export_v1/torch_cuda_parity.json'
    $needsCudaGate = $true
    if (Test-Path -LiteralPath $cudaGatePath) {
        $gate = Get-Content -LiteralPath $cudaGatePath -Raw | ConvertFrom-Json
        if ($gate.status -eq 'passed' -and $gate.original_tf24_comparison.status -eq 'passed') { $needsCudaGate = $false }
    }
    if ($needsCudaGate) {
        # The runner refuses agile episodes until this gate exists, so it must be
        # produced before admission; it is a real GPU inference comparison against
        # the original TF2.4 outputs, not a timing-only probe.
        Write-Stage 'admission' 'producing the Agile CUDA parity evidence required by the agile backend'
        docker compose --profile training run --rm train python3 scripts/probe_agile_torch.py --device cuda *> (Join-Path $logDir 'post_training_agile_cuda_parity.log')
        Write-Stage 'admission' ('agile cuda parity exit ' + $LASTEXITCODE)
        if ($LASTEXITCODE -ne 0) { throw 'Agile CUDA parity failed; the agile backend cannot pass admission' }
    }
    else { Write-Stage 'admission' 'Agile CUDA parity already passed; reusing the recorded evidence' }
    Write-Stage 'admission' 'recording runtime admission (phase A then phase B)'
    & $python scripts/record_runtime_validation.py --phase ab *> (Join-Path $logDir 'post_training_runtime_admission.log')
    if ($LASTEXITCODE -ne 0) { throw 'Runtime admission failed; the matrix must not start' }
    Write-Stage 'admission' 'runtime admission passed for the validated backends'
}

if ($requested -contains 'matrix') {
    if (-not $MatrixArguments) { throw 'Matrix stage requires -MatrixArguments with the driver arguments' }
    $live = docker ps -q --filter 'name=yopo-formal-seed'
    if ($live) { Write-Stage 'matrix' 'refused: a formal trainer is live'; throw 'A formal trainer is live; the matrix must wait for the GPU' }
    Write-Stage 'matrix' ('running matrix driver with: ' + $MatrixArguments)
    $matrixArgs = @((Join-Path $PSScriptRoot 'run_benchmark_matrix.py')) + ($MatrixArguments -split '\s+' | Where-Object { $_ })
    & $python @matrixArgs *> (Join-Path $logDir 'post_training_matrix.log')
    if ($LASTEXITCODE -ne 0) { throw 'Matrix driver returned a non-zero status' }
    Write-Stage 'matrix' 'matrix batch finished'
}

if ($requested -contains 'showcase') {
    $live = docker ps -q --filter 'name=yopo-formal-seed'
    if ($live) { Write-Stage 'showcase' 'refused: a formal trainer is live'; throw 'A formal trainer is live; the final showcase must wait for the GPU' }
    Write-Stage 'showcase' 'running the final-weight showcase'
    & pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'run_final_showcase.ps1') -RunPrefix $RunPrefix *> (Join-Path $logDir 'post_training_showcase.log')
    Write-Stage 'showcase' ('showcase exit ' + $LASTEXITCODE)
}

if ($requested -contains 'aggregate') {
    docker compose --profile cpu-tools run --rm cpu-tools python3 scripts/aggregate_benchmarks.py *> (Join-Path $logDir 'post_training_aggregate.log')
    Write-Stage 'aggregate' ('aggregate exit ' + $LASTEXITCODE)
}

if ($requested -contains 'figures') {
    docker compose --profile cpu-tools run --rm cpu-tools python3 scripts/make_paper_figures.py *> (Join-Path $logDir 'post_training_figures.log')
    Write-Stage 'figures' ('figures/tables regenerated, exit ' + $LASTEXITCODE)
}

if ($requested -contains 'docs') {
    & $python scripts/audit_command_evidence.py *> (Join-Path $logDir 'post_training_docs_audit.log')
    Write-Stage 'docs' ('command/evidence audit exit ' + $LASTEXITCODE)
}

if ($requested -contains 'dagger') {
    $live = docker ps -q --filter 'name=yopo-formal-seed'
    if ($live) { Write-Stage 'dagger' 'refused: a formal trainer is live'; throw 'A formal trainer is live; the DAgger collection must wait for the GPU' }
    $daggerCheckpoint = 'checkpoints/' + $RunPrefix + '_seed0/best_policy.pth'
    if (-not (Test-Path -LiteralPath $daggerCheckpoint)) { throw 'DAgger collection needs the audited seed0 checkpoint' }
    if (-not (Test-Path -LiteralPath ('checkpoints/' + $RunPrefix + '_seed0/training_audit.json'))) { throw 'DAgger collection needs the seed0 training audit' }
    Write-Stage 'dagger' 'step 1/5 collecting on-policy rollouts'
    & $python scripts/run_dagger_collection.py --run dagger_agg_v1 --checkpoint ($RunPrefix + '_seed0/best_policy.pth') `
        --map-seeds 7000-7015 --flights-per-map 3 --speeds 1.5,2.5,3.5 --durations 20,30 `
        *> (Join-Path $logDir 'post_training_dagger_collection.log')
    Write-Stage 'dagger' ('collection exit ' + $LASTEXITCODE)
    if (-not (Test-Path -LiteralPath 'artifacts/dagger_flights/dagger_agg_v1/flights.json')) {
        Write-Stage 'dagger' 'collection produced no manifest; stopping the DAgger stage'
    }
    else {
        if (Test-Path -LiteralPath 'datasets/isaac_dagger_v1/aggregation_manifest.json') {
            Write-Stage 'dagger' 'aggregation dataset already built; skipping the build step'
        }
        else {
        Write-Stage 'dagger' 'step 2/5 building the aggregation dataset (host python, reference SDF through docker)'
        & $python scripts/build_dagger_dataset.py --base (Join-Path $projectPath 'datasets/isaac_full_v1') `
            --flights (Join-Path $projectPath 'artifacts/dagger_flights/dagger_agg_v1') `
            --output (Join-Path $projectPath 'datasets/isaac_dagger_v1') --allow-map-seeds 7000-7015 `
            --qa-frames 30 --self-check-frame 0 *> (Join-Path $logDir 'post_training_dagger_build.log')
        Write-Stage 'dagger' ('build exit ' + $LASTEXITCODE)
        }
        Write-Stage 'dagger' 'step 3/5 validating the aggregation dataset in the container'
        docker compose --profile cpu-tools run --rm cpu-tools python3 scripts/validate_dataset.py --dataset /workspace/datasets/isaac_dagger_v1 *> (Join-Path $logDir 'post_training_dagger_validate.log')
        Write-Stage 'dagger' ('validate exit ' + $LASTEXITCODE)
        Write-Stage 'dagger' 'step 4/5 staging the aggregation dataset into the data volume'
        docker compose --profile training run --rm train python3 scripts/stage_aggregation_dataset.py --name isaac_dagger_v1 *> (Join-Path $logDir 'post_training_dagger_stage.log')
        Write-Stage 'dagger' ('stage exit ' + $LASTEXITCODE)
        if (Test-Path -LiteralPath ('checkpoints/dagger_main_v1_seed0/result.json')) {
            Write-Stage 'dagger' 'fine-tuned run already complete; skipping the fine-tune step'
        }
        else {
        Write-Stage 'dagger' 'step 5/5 fine-tuning from the audited base checkpoint'
        docker compose --profile training run --rm --name yopo-dagger-seed0 train python3 scripts/train_dagger_finetune.py --dataset /data/isaac_dagger_v1 --run dagger_main_v1_seed0 --seed 0 --epochs 10 --base-run ${RunPrefix}_seed0 *> (Join-Path $logDir 'post_training_dagger_finetune.log')
        Write-Stage 'dagger' ('finetune exit ' + $LASTEXITCODE)
        }
    }
}

if ($requested -contains 'acceptance') {
    & $python scripts/final_acceptance_audit.py --run-prefix $RunPrefix *> (Join-Path $logDir 'post_training_acceptance_audit.log')
    Write-Stage 'acceptance' ('final acceptance audit exit ' + $LASTEXITCODE)
    & $python scripts/make_status_overview.py --run-prefix $RunPrefix *> (Join-Path $logDir 'post_training_status_overview.log')
    Write-Stage 'acceptance' ('status overview exit ' + $LASTEXITCODE)
}

Write-Stage 'done' ('stages requested: ' + ($requested -join ','))
