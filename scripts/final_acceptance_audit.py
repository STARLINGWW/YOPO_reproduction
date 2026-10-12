"""Mechanical audit of the eight acceptance items against authoritative evidence.

Every item reports one of: verified (evidence proves it), pending (some evidence
exists but the item is not finished), missing_evidence (the required artifact
does not exist yet), or documented_gap (the protocol records the item as
explicitly not satisfied). Nothing is inferred from intent or from a plan.
"""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from yopo_repro.io import sha256_file,write_json_atomic


def read_json(path):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception:return None


def item(id_,requirement,status,detail,evidence=None):
    return {'id':id_,'requirement':requirement,'status':status,'detail':detail,
            'evidence':[str(p) for p in (evidence or [])]}


def seeds_folder(prefix,seed):return ROOT/'checkpoints'/('%s_seed%d'%(prefix,seed))


def check_three_seed_training(prefix):
    rows = [];missing = [];pending = []
    for seed in 0,1,2:
        folder = seeds_folder(prefix,seed)
        audit = read_json(folder/'training_audit.json');result = read_json(folder/'result.json')
        epochs = sum(1 for epoch in range(1,51) if (folder/('epoch_%03d.pt'%epoch)).is_file())
        policies = sum(1 for epoch in range(1,51) if (folder/('policy_epoch_%03d.pth'%epoch)).is_file())
        if (audit and audit.get('status')=='passed' and result and result.get('status')=='complete'
                and result.get('steps')==312500 and epochs==50 and policies==50):
            rows.append({'seed':seed,'audit':'passed','steps':result['steps'],'epoch_files':epochs,
                         'policy_files':policies,'best_epoch':audit.get('selection',{}).get('best_epoch')})
        else:
            pending.append({'seed':seed,'audit':(audit or {}).get('status'),'result':(result or {}).get('status'),
                            'epoch_files':epochs,'policy_files':policies})
    if not pending:
        return item('three_seed_training','Three seeds each trained 50 epochs from scratch and passed the strict per-epoch audit',
                    'verified','all three seeds audited',[seeds_folder(prefix,s)/'training_audit.json' for s in (0,1,2)])
    return item('three_seed_training','Three seeds each trained 50 epochs from scratch and passed the strict per-epoch audit',
                'pending','seeds without a passed audit: %s'%[r['seed'] for r in pending],
                [seeds_folder(prefix,s)/'result.json' for s in (0,1,2)])


def check_expert_comparison(prefix):
    files = {seed:(ROOT/'artifacts/expert'/('network_comparison_trained_seed%d.json'%seed)) for seed in (0,1,2)}
    random_initial = ROOT/'artifacts/expert/network_comparison_random_initial.json'
    details = {};verified = True;any_present = False
    for name,path in list(files.items())+[('random_initial',random_initial)]:
        data = read_json(path)
        if not data:details['seed_%s'%name] = 'missing';verified = False;continue
        any_present = True
        samples = data.get('samples');alignment = data.get('sample_alignment_max_abs_error')
        ok = samples==10000 and (alignment is not None and alignment<=1e-9) and data.get('status')=='complete'
        details['seed_%s'%name] = {'samples':samples,'alignment_max_abs_error':alignment,'status':data.get('status'),'acceptable':ok}
        verified = verified and ok
    if verified:
        return item('expert_50_step_comparison','Expert comparison on the independent offline test set with the audited final weights',
                    'verified','three seeds plus random initial at full sample count',list(files.values())+[random_initial])
    if any_present:
        return item('expert_50_step_comparison','Expert comparison on the independent offline test set with the audited final weights',
                    'pending','final-weight reruns not complete',[p for p in list(files.values())+[random_initial] if p.is_file()])
    return item('expert_50_step_comparison','Expert comparison on the independent offline test set with the audited final weights',
                'missing_evidence','no comparison JSON present',list(files.values())+[random_initial])


def check_native_validation():
    admission_path = ROOT/'benchmarks/protocol_v1/runtime_validation.json'
    admission = read_json(admission_path)
    agile_cuda = read_json(ROOT/'artifacts/agile_autonomy/torch_export_v1/torch_cuda_parity.json')
    parts = {'runtime_admission':admission.get('status') if admission else 'missing',
             'validated_backends':admission.get('validated_backends') if admission else [],
             'agile_cuda_parity':(agile_cuda or {}).get('status')}
    if admission and admission.get('status')=='passed' and (agile_cuda or {}).get('status')=='passed':
        return item('baseline_native_validation','Baseline CUDA/native closed-loop validation before the matrix',
                    'verified','admission passed and agile CUDA parity passed',[admission_path])
    return item('baseline_native_validation','Baseline CUDA/native closed-loop validation before the matrix',
                'pending' if admission else 'missing_evidence',json.dumps(parts,ensure_ascii=False),
                [admission_path,ROOT/'artifacts/agile_autonomy/torch_export_v1/torch_cuda_parity.json'])


def check_mppi():
    protocol = read_json(ROOT/'configs/reproduction_protocol.json') or {}
    status = (((protocol.get('baseline_sources') or {}).get('MPPI') or {}).get('status')) or 'unknown'
    evidence = ROOT/'artifacts/paper_sources/mppi_identity.json'
    return item('mppi_reference17','Reference-17 MPPI baseline either reproduced from the paper or explicitly recorded as unfilled',
                'documented_gap' if 'reference_only' in status else 'pending','protocol status: %s'%status,[evidence])


def check_dagger():
    dataset = ROOT/'datasets/isaac_dagger_v1/aggregation_manifest.json'
    finetune = read_json(ROOT/'checkpoints/dagger_main_v1_seed0/result.json')
    manifest = read_json(dataset)
    if manifest and finetune and finetune.get('status')=='complete':
        return item('dagger_finetune','Separate DAgger aggregation data version and fine-tuned checkpoint',
                    'verified','aggregation dataset and fine-tuned run both complete',[dataset,ROOT/'checkpoints/dagger_main_v1_seed0/result.json'])
    if manifest or (ROOT/'src/yopo_dagger/build_dataset.py').is_file():
        return item('dagger_finetune','Separate DAgger aggregation data version and fine-tuned checkpoint',
                    'pending','pipeline implemented; GPU collection/fine-tune not executed yet',
                    [ROOT/'src/yopo_dagger/build_dataset.py',ROOT/'scripts/train_dagger_finetune.py'])
    return item('dagger_finetune','Separate DAgger aggregation data version and fine-tuned checkpoint',
                'missing_evidence','no aggregation dataset or fine-tune run',[dataset])


def check_matrix():
    summary = read_json(ROOT/'artifacts/benchmark_summary/summary.json')
    result = read_json(ROOT/'artifacts/benchmark_summary/matrix_result.json')
    plan = read_json(ROOT/'artifacts/benchmark_summary/plan.json')
    completed = (summary or {}).get('completed_episodes');expected = (summary or {}).get('expected_episodes')
    failures = len((result or {}).get('failures') or []) if result else None
    invalid = len((summary or {}).get('invalid_evidence') or [])
    duplicates = len((summary or {}).get('duplicate_primary_attempts') or [])
    aggregate_clean = (summary or {}).get('status')=='outcome_coverage_complete'
    if summary and completed==expected==1800 and failures==0 and invalid==0 and duplicates==0 and aggregate_clean:
        return item('benchmark_matrix','Frozen 1800-episode matrix executed with coverage-aware failure statistics',
                    'verified','all 1800 episodes have terminal evidence, no invalid or duplicate primary evidence, and the aggregate reports outcome_coverage_complete',
                    [ROOT/'artifacts/benchmark_summary/summary.json'])
    detail = 'completed=%s expected=%s driver_failures=%s invalid_evidence=%s duplicates=%s aggregate_status=%s plan_pending=%s'%(
        completed,expected,failures,invalid,duplicates,(summary or {}).get('status'),(plan or {}).get('pending_episodes'))
    return item('benchmark_matrix','Frozen 1800-episode matrix executed with coverage-aware failure statistics',
                'pending' if plan else 'missing_evidence',detail,
                [ROOT/'artifacts/benchmark_summary/summary.json',ROOT/'artifacts/benchmark_summary/plan.json'])


def check_showcase_and_audit():
    audit = read_json(ROOT/'artifacts/environment/command_evidence_audit.json')
    audited = {}
    for seed in 0,1,2:
        seed_audit = read_json(seeds_folder('formal_main_v1',seed)/'training_audit.json')
        if seed_audit and seed_audit.get('status')=='passed':
            audited[seed_audit['selection']['best_policy_file_sha256']] = seed
    showcase_runs = sorted((ROOT/'artifacts/ros2_showcase').glob('*')) if (ROOT/'artifacts/ros2_showcase').is_dir() else []
    matched = []
    for folder in showcase_runs:
        manifest = read_json(folder/'render_manifest.json')
        if not manifest:continue
        digest = manifest.get('checkpoint_sha256')
        if digest and digest in audited:
            video = Path(str(manifest.get('video') or ''))
            if video.is_file() and manifest.get('navigation_status')=='success':
                matched.append({'folder':str(folder.relative_to(ROOT)),'seed':audited[digest],'video':str(video)})
    if audit and audit.get('status')=='passed' and matched:
        return item('final_showcase_and_audit','Final 50-epoch showcase plus a passing command/evidence audit',
                    'verified','showcase runs trace to audited checkpoints and the command/evidence audit passes',
                    [ROOT/'artifacts/environment/command_evidence_audit.json']+[ROOT/m['folder']/'render_manifest.json' for m in matched])
    if audit and audit.get('status')=='passed':
        return item('final_showcase_and_audit','Final 50-epoch showcase plus a passing command/evidence audit',
                    'pending','command/evidence audit passes; no showcase run is tied to an audited checkpoint yet',
                    [ROOT/'artifacts/environment/command_evidence_audit.json'])
    return item('final_showcase_and_audit','Final 50-epoch showcase plus a passing command/evidence audit',
                'missing_evidence','no passing command/evidence audit record',
                [ROOT/'artifacts/environment/command_evidence_audit.json'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-prefix',default='formal_main_v1')
    parser.add_argument('--output',default='artifacts/environment/final_acceptance_audit.json')
    parser.add_argument('--root',default=None,help='Override the project root (used by tests)')
    args = parser.parse_args()
    global ROOT
    if args.root:ROOT = Path(args.root).resolve()
    checks = [check_three_seed_training(args.run_prefix),check_expert_comparison(args.run_prefix),
              check_native_validation(),check_mppi(),check_dagger(),check_matrix(),check_showcase_and_audit()]
    counts = {}
    for check in checks:counts[check['status']] = counts.get(check['status'],0)+1
    report = {'version':1,'scope':'mechanical acceptance audit; each item lists the authoritative evidence inspected',
              'run_prefix':args.run_prefix,'items':checks,'counts':counts,
              'all_verified':all(check['status']=='verified' for check in checks)}
    write_json_atomic(ROOT/args.output,report)
    for check in checks:print('%-28s %-18s %s'%(check['id'],check['status'],check['detail'][:110]))
    print(json.dumps(counts,ensure_ascii=False))


if __name__=='__main__':main()
