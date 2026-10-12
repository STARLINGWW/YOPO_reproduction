"""One-command, read-only status of the three-seed queue and its guards.

Reports only what the authoritative files say: per-seed progress, whether the
strict audit exists, how many epoch/policy checkpoint files are present, whether
the audited validation-selected model hash matches the audit record, and which
formal containers are live. It never starts, stops or writes anything.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception:return None


def sha256(path):
    try:
        digest = hashlib.sha256()
        with Path(path).open('rb') as handle:
            for block in iter(lambda:handle.read(4*1024*1024),b''):digest.update(block)
        return digest.hexdigest()
    except Exception:return None


def container_state():
    try:
        out = subprocess.run(['docker','ps','--format','{{.Names}}'],capture_output=True,text=True)
        if out.returncode!=0:return {'error':'docker ps failed'}
        return {'live':[name for name in out.stdout.split() if name.startswith('yopo')]}
    except FileNotFoundError:
        return {'error':'docker CLI unavailable'}


def seed_row(prefix,seed):
    folder = ROOT/'checkpoints'/('%s_seed%d'%(prefix,seed))
    progress = read(folder/'progress.json') or {}
    result = read(folder/'result.json')
    audit = read(folder/'training_audit.json')
    epochs = sum(1 for index in range(1,51) if (folder/('epoch_%03d.pt'%index)).is_file())
    policies = sum(1 for index in range(1,51) if (folder/('policy_epoch_%03d.pth'%index)).is_file())
    best = folder/'best_policy.pth'
    row = {'seed':seed,'progress_status':progress.get('status'),'epochs_completed':progress.get('epoch_completed'),
           'step':progress.get('step'),'result':(result or {}).get('status'),'steps_recorded':(result or {}).get('steps'),
           'audit':(audit or {}).get('status'),'best_epoch':((audit or {}).get('selection') or {}).get('best_epoch'),
           'epoch_files':epochs,'policy_files':policies,'folder_exists':folder.is_dir()}
    if audit and best.is_file():
        digest = sha256(best)
        row['best_policy_matches_audit'] = digest==audit['selection']['best_policy_file_sha256']
        row['best_policy_sha256'] = digest
    return row


def epoch_durations(folder,window=8):
    """Measured wall time per completed epoch, from the authoritative metrics file."""
    rows = []
    path = Path(folder)/'metrics.jsonl'
    if not path.is_file():return rows
    for line in path.read_text(encoding='utf-8').splitlines():
        try:row = json.loads(line)
        except Exception:continue
        if row.get('kind')=='epoch':rows.append(float(row['wall_elapsed_s']))
    durations = [b-a for a,b in zip(rows,rows[1:]) if b>a]
    if rows and not durations:durations = [rows[-1]/max(len(rows),1)]
    return durations[-window:]


def projected_finish(rows,prefix,remaining_epochs_per_seed=None):
    """Project the queue finish from the measured epoch time of the live seed."""
    running = next((row for row in rows if row['progress_status']=='running'),None)
    if not running:return None
    folder = ROOT/'checkpoints'/('%s_seed%d'%(prefix,running['seed']))
    durations = epoch_durations(folder)
    if not durations:return None
    mean = sum(durations)/len(durations)
    remaining = 50-(running['epochs_completed'] or 0)
    leftover = sum((50-(row['epochs_completed'] or 0)) for row in rows if row['seed']>running['seed'])
    total_seconds = (remaining+leftover)*mean
    import datetime
    finish = datetime.datetime.now().astimezone()+datetime.timedelta(seconds=total_seconds)
    return {'mean_epoch_seconds':mean,'epochs_measured':len(durations),'remaining_epochs_this_seed':remaining,
            'remaining_epochs_after':leftover,'projected_hours':total_seconds/3600.,
            'projected_finish_local':finish.isoformat(timespec='minutes')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-prefix',default='formal_main_v1')
    parser.add_argument('--json',action='store_true',help='print JSON instead of a short table')
    args = parser.parse_args()
    rows = [seed_row(args.run_prefix,seed) for seed in (0,1,2)]
    containers = container_state()
    admission = read(ROOT/'benchmarks/protocol_v1/runtime_validation.json')
    projection = projected_finish(rows,args.run_prefix)
    payload = {'recorded_at':__import__('datetime').datetime.now().astimezone().isoformat(),
               'seeds':rows,'containers':containers,'projection':projection,
               'runtime_admission':{'present':admission is not None,'status':(admission or {}).get('status')},
               'matrix_progress_exists':(ROOT/'artifacts/benchmark_summary/matrix_progress.json').is_file(),
               'post_training_sentinel':(ROOT/'artifacts/environment/post_training_pipeline_launched.json').is_file()}
    if args.json:
        print(json.dumps(payload,indent=2,ensure_ascii=False));return
    print('seed  progress   epochs  step      result      audit      files(epoch/policy)  hash-match')
    for row in rows:
        print('%-5s %-10s %-7s %-9s %-11s %-10s %-19s %s'%(row['seed'],row['progress_status'] or '-',
              '%s/50'%(row['epochs_completed'] if row['epochs_completed'] is not None else '-'),row['step'] or '-',
              row['result'] or 'pending',row['audit'] or 'pending','%s/%s'%(row['epoch_files'],row['policy_files']),
              row.get('best_policy_matches_audit','n/a')))
    print('live formal containers:',containers.get('live') or containers.get('error') or 'none')
    print('runtime admission:',payload['runtime_admission']['status'] or 'missing',
          '| matrix ledger:','yes' if payload['matrix_progress_exists'] else 'no',
          '| post-training chain started:','yes' if payload['post_training_sentinel'] else 'no')
    if projection:
        print('measured epoch %.0fs (last %d) -> %d + %d epochs left: about %.1f h, finish ~%s'%(
            projection['mean_epoch_seconds'],projection['epochs_measured'],projection['remaining_epochs_this_seed'],
            projection['remaining_epochs_after'],projection['projected_hours'],projection['projected_finish_local']))


if __name__=='__main__':main()
