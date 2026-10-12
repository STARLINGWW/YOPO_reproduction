"""Turn real native flights into benchmarks/protocol_v1/runtime_validation.json.

The native runner refuses any frozen episode until an admission record exists,
so admission is bootstrapped honestly in two phases:

  phase A  runs development-scope native flights for every requested backend
           (real Isaac PhysX + real ROS2 planner container) and writes a
           provisional record containing only what those runs proved;
  phase B  replays a small number of real frozen episodes through the
           episode-id path, appends their evidence and downgrades the record to
           failed if any of them does not pass.

Episodes consumed by phase B are recorded in consumed_episode_ids so the matrix
driver can skip them instead of producing duplicate primary attempts.
"""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from yopo_repro.io import sha256_file,write_json_atomic
from yopo_sim.job_guard import require_training_gpu_released

ISAAC_PYTHON = os.environ.get('YOPO_ISAAC_PYTHON',r'D:\_AAA_FILE_ALL\Anaconda_file\Anaconda_env\isaac61\python.exe')
BACKENDS = {
    'yopo_seed0':{'backend':'yopo','device':'cuda','checkpoint':'formal_main_v1_seed0/best_policy.pth',
                  'model':'yopo_seed0'},
    'agile_autonomy':{'backend':'agile','device':'cuda','model':'agile_autonomy'},
    'topotraj':{'backend':'topotraj','device':'cpu','model':'topotraj',
                'topo-config':'configs/topotraj/isaac_development.yaml'},
}
RUNTIME_FILES = ['scripts/run_ros2_navigation.py','scripts/ros2/serve_planner.py',
    'scripts/validate_ros2_flight.py','scripts/evaluate_ros2_flight.py','scripts/run_benchmark_matrix.py',
    'src/yopo_sim/trajectory_buffer.py','src/yopo_sim/unified_quad.py',
    'src/yopo_sim/physx_vehicle.py','src/yopo_sim/evaluation_geometry.py','src/yopo_sim/resource_sampler.py',
    'src/yopo_sim/job_guard.py','src/yopo_eval/task_spec.py','src/yopo_eval/metrics.py',
    'src/yopo_repro/forest.py','configs/unified_quad.json','configs/topotraj/isaac_development.yaml',
    'ros2_ws/src/yopo_runtime/yopo_runtime/protocol_node.py','ros2_ws/src/yopo_runtime/yopo_runtime/main_planner.py',
    'ros2_ws/src/yopo_runtime/yopo_runtime/agile_planner.py','ros2_ws/src/yopo_runtime/yopo_runtime/frame_gate.py']


def runtime_file_hashes():
    hashes = {}
    for name in RUNTIME_FILES:
        path = ROOT/name
        if not path.is_file():raise FileNotFoundError('Frozen runtime file missing: '+name)
        hashes[name] = sha256_file(path)
    return hashes


def pick_episodes(protocol,model,count):
    episodes = [dict(e) for e in protocol['episodes'] if e['model']==model]
    episodes.sort(key=lambda e:(e['speed_mps'],e['task_index']))
    chosen = [];seeds = set()
    for episode in episodes:
        task = protocol['tasks'][episode['task_index']]
        if task['map_seed'] in seeds:continue
        chosen.append(episode);seeds.add(task['map_seed'])
        if len(chosen)==count:break
    return chosen


def native_command(run_name,key,extra):
    config = BACKENDS[key]
    command = [ISAAC_PYTHON,str(ROOT/'scripts/run_ros2_navigation.py'),'--run',run_name,
               '--backend',config['backend'],'--device',config['device']]
    if config.get('checkpoint'):command += ['--checkpoint',config['checkpoint']]
    if config.get('topo-config'):command += ['--topo-config',config['topo-config']]
    return command+list(extra)


def run_native(run_name,key,extra):
    log = ROOT/'artifacts/environment'/(run_name+'.log')
    env = os.environ.copy();env['OMNI_KIT_ACCEPT_EULA'] = 'YES'
    with log.open('a',encoding='utf-8') as handle:
        completed = subprocess.run(native_command(run_name,key,extra),cwd=ROOT,env=env,
                                   stdout=handle,stderr=subprocess.STDOUT)
    steps = {}
    for name,script in [('validate','scripts/validate_ros2_flight.py'),('evaluate','scripts/evaluate_ros2_flight.py')]:
        outcome = subprocess.run([ISAAC_PYTHON,str(ROOT/script),'--run',run_name],cwd=ROOT,capture_output=True,text=True)
        (ROOT/'artifacts/environment'/(run_name+'_'+name+'.log')).write_text(outcome.stdout+outcome.stderr,encoding='utf-8')
        steps[name+'_returncode'] = int(outcome.returncode)
    return {'returncode':int(completed.returncode),'log':str(log.relative_to(ROOT).as_posix()),**steps}


def verify_run(run_name,key,root=None):
    root = Path(root or ROOT)
    output = root/'artifacts/ros2_flights'/run_name
    metrics_path = output/'metrics.json'
    if not metrics_path.is_file():raise RuntimeError('Missing flight metrics for '+run_name)
    metrics = json.loads(metrics_path.read_text(encoding='utf-8'))
    planner_path = output/'planner_status.json'
    planner = json.loads(planner_path.read_text(encoding='utf-8')) if planner_path.is_file() else {}
    stats = planner.get('stats',{})
    problems = []
    if metrics.get('status') in (None,'crashed','interrupted','running','no_metrics'):
        problems.append('flight status %s'%metrics.get('status'))
    if not metrics.get('interface_passed'):problems.append('interface_passed is not true')
    buffer_stats = metrics.get('buffer_stats',{})
    if int(buffer_stats.get('applied',0))<3:problems.append('applied trajectories below 3')
    if stats:
        if int(stats.get('planner_errors',0)):problems.append('planner errors reported')
        if int(stats.get('wrong_episode',0)):problems.append('wrong-episode responses reported')
        if int(stats.get('stale_result',0)):problems.append('stale results reported')
    if not int(metrics.get('frames') or 0):problems.append('no depth frames recorded')
    validation_path = output/'validation.json'
    evidence = {'run':run_name,'backend':key,'status':metrics.get('status'),
                'interface_passed':metrics.get('interface_passed'),'frames':metrics.get('frames'),
                'applied_trajectories':buffer_stats.get('applied'),
                'planner_errors':stats.get('planner_errors'),'wrong_episode':stats.get('wrong_episode'),
                'max_speed_mps':metrics.get('max_speed_mps'),'min_net_clearance_m':metrics.get('min_net_clearance_m'),
                'real_time_factor':metrics.get('real_time_factor'),'goal_error_m':metrics.get('goal_error_m'),
                'metrics_path':str(metrics_path.relative_to(root).as_posix()),'metrics_sha256':sha256_file(metrics_path)}
    if validation_path.is_file():
        validation = json.loads(validation_path.read_text(encoding='utf-8'))
        evidence['validation_path'] = str(validation_path.relative_to(root).as_posix())
        evidence['validation_sha256'] = sha256_file(validation_path)
        evidence['validation_status'] = validation.get('status')
        if validation.get('status')!='passed':problems.append('independent validation status %s'%validation.get('status'))
    else:problems.append('missing independent validation.json')
    evaluation_path = output/'evaluation.json'
    if evaluation_path.is_file():
        evaluation = json.loads(evaluation_path.read_text(encoding='utf-8'))
        evidence['evaluation_path'] = str(evaluation_path.relative_to(root).as_posix())
        evidence['evaluation_sha256'] = sha256_file(evaluation_path)
        evidence['metrics_available'] = evaluation.get('metrics_available')
        evidence['instrumentation_gaps'] = evaluation.get('instrumentation_gaps')
        if evaluation.get('metrics_available') is not True:problems.append('flight metrics could not be evaluated')
    else:problems.append('missing evaluation.json')
    evidence['problems'] = problems
    if problems:raise RuntimeError('Admission run failed: %s: %s'%(run_name,'; '.join(problems)))
    return evidence


def expected_checkpoint(key):
    config = BACKENDS[key]
    if not config.get('checkpoint'):return None
    folder = (ROOT/'checkpoints'/config['checkpoint']).resolve()
    audit = json.loads((folder.parent/'training_audit.json').read_text(encoding='utf-8'))
    return {'checkpoint':config['checkpoint'],'file_sha256':sha256_file(folder),
            'audited_selection_sha256':audit['selection']['best_policy_file_sha256'],
            'audit_status':audit['status'],'epochs':audit['epochs']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--backends',default='yopo_seed0,agile_autonomy,topotraj')
    parser.add_argument('--protocol',type=Path,default=ROOT/'benchmarks/protocol_v1/protocol.json')
    parser.add_argument('--phase',choices=['a','b','ab'],default='ab')
    parser.add_argument('--dev-map-seed',type=int,default=3000)
    parser.add_argument('--dev-speed',type=float,default=2.)
    parser.add_argument('--dev-duration',type=float,default=20.)
    parser.add_argument('--episodes-per-backend',type=int,default=2)
    parser.add_argument('--stamp',default=time.strftime('%Y%m%d_%H%M%S'))
    args = parser.parse_args()
    require_training_gpu_released()
    keys = [v.strip() for v in args.backends.split(',') if v.strip()]
    unknown = [k for k in keys if k not in BACKENDS]
    if unknown:raise ValueError('Unknown backends: %s'%unknown)
    protocol_path = args.protocol.resolve()
    protocol_raw = protocol_path.read_bytes()
    protocol = json.loads(protocol_raw)
    admission_path = protocol_path.parent/'runtime_validation.json'
    record = {'version':1,'status':'pending','protocol_sha256':None,'validated_backends':[],
              'runtime_files':{},'phase_a':{},'phase_b':{},'consumed_episode_ids':[],
              'recorded_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
              'scope':'native Isaac/ROS2 runtime admission for the frozen task matrix; not a success-rate result',
        'rule':'validated_backends lists the mission backend names used by the frozen protocol '
               '(yopo/agile/topotraj), and only when that backend\'s own real runs passed every check; '
               'validated_backend_keys keeps the admission keys (yopo_seed0/agile_autonomy/topotraj)'}
    import hashlib
    record['protocol_sha256'] = hashlib.sha256(protocol_raw).hexdigest()
    record['runtime_files'] = runtime_file_hashes()
    checkpoints = {}
    for key in keys:
        if BACKENDS[key].get('checkpoint'):checkpoints[key] = expected_checkpoint(key)
    record['checkpoints'] = checkpoints
    failures = []
    if 'a' in args.phase:
        for key in keys:
            run_name = 'rv_dev_%s_%s'%(key,args.stamp)
            result = run_native(run_name,key,['--map-seed',str(args.dev_map_seed),'--speed',str(args.dev_speed),
                                              '--duration',str(args.dev_duration),'--scope',
                                              'runtime_validation_admission_not_matrix'])
            entry = {'run':run_name,**result,'scope':'development_runtime_admission'}
            try:entry['evidence'] = verify_run(run_name,key)
            except RuntimeError as exc:
                entry['problems'] = str(exc);failures.append('%s phase A: %s'%(key,exc))
            record['phase_a'][key] = entry
            write_json_atomic(admission_path,record)
        passed = [k for k in keys if 'evidence' in record['phase_a'].get(k,{})]
        # Consumers compare against the mission backend name from the frozen
        # protocol (src/yopo_eval/task_spec.resolve_episode -> 'yopo'/'agile'/
        # 'topotraj'): verify_runtime_admission, the matrix driver's skip check
        # and the aggregator's admission assertion all use that name. The
        # admission keys ('yopo_seed0', 'agile_autonomy') must therefore never
        # leak into validated_backends.
        record['validated_backends'] = sorted({BACKENDS[k]['backend'] for k in passed})
        record['validated_backend_keys'] = list(passed)
        record['status'] = 'passed' if passed==keys else 'failed'
        record['provisional'] = True
        write_json_atomic(admission_path,record)
        if passed!=keys:
            raise SystemExit('Phase A failed for %s; admission record left as failed'%[k for k in keys if k not in passed])
    if 'b' in args.phase:
        existing = json.loads(admission_path.read_text(encoding='utf-8'))
        if existing.get('status')!='passed':
            raise SystemExit('Phase B requires a passed provisional admission record')
        record = existing;record['provisional'] = False
        for key in keys:
            for episode in pick_episodes(protocol,BACKENDS[key]['model'],args.episodes_per_backend):
                run_name = 'rv_frozen_%s_%s'%(episode['id'],args.stamp)
                result = run_native(run_name,key,['--episode-id',episode['id']])
                entry = {'run':run_name,'episode_id':episode['id'],'speed_mps':episode['speed_mps'],**result}
                try:
                    entry['evidence'] = verify_run(run_name,key)
                    record['consumed_episode_ids'].append(episode['id'])
                except RuntimeError as exc:
                    entry['problems'] = str(exc);failures.append('%s phase B %s: %s'%(key,episode['id'],exc))
                record['phase_b'][episode['id']] = entry
                write_json_atomic(admission_path,record)
        record['status'] = 'passed' if not failures else 'failed'
        record['failures'] = failures
        record['recorded_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        write_json_atomic(admission_path,record)
    print(json.dumps({'status':record['status'],'validated_backends':record['validated_backends'],
                      'consumed_episode_ids':record['consumed_episode_ids'],'failures':failures},indent=2,ensure_ascii=False))
    if failures:raise SystemExit('Runtime admission failed; the matrix must not start')


if __name__=='__main__':main()
