"""Resume-safe driver for the frozen 1800-episode task matrix.

Default mode is a dry run: it resolves every selected episode through the
frozen protocol, writes a plan with the projected serial wall time, and touches
nothing else. Real execution requires --execute, refuses to start while a
formal trainer holds the GPU, refuses to start without a passed runtime
admission record, runs one Isaac process at a time, skips episodes that already
have terminal evidence (including the episodes consumed by runtime admission),
and never overwrites primary evidence.
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
from yopo_eval.task_spec import resolve_episode
from yopo_sim.job_guard import require_training_gpu_released

ISAAC_PYTHON = os.environ.get('YOPO_ISAAC_PYTHON','python')
TERMINAL = {'success','collision','timeout','crashed','out_of_map'}
REFERENCE_FLIGHT = {'path_length_m':25.244946988194357,'sim_duration_s':17.06400081049651,
                    'wall_runtime_s':39.44799740007147,'real_time_factor':0.4325695075833074,
                    'source':'artifacts/ros2_flights/ros2_scratch_checkpoint_20260924_061715/metrics.json'}
STARTUP_OVERHEAD_S = 20.
STARTUP_OVERHEAD_EVIDENCE = ('planner container lifetime 54.03s minus flight wall 39.45s in '
                             'artifacts/ros2_flights/ros2_scratch_checkpoint_20260924_061715/planner_status.json '
                             'bounds pre-flight overhead at about 15s; 20s is used as a conservative constant')


def load_protocol(path):
    raw = Path(path).resolve().read_bytes()
    protocol = json.loads(raw)
    import hashlib
    return protocol,hashlib.sha256(raw).hexdigest()


def display_path(path):
    resolved = Path(path).resolve()
    try:return str(resolved.relative_to(ROOT).as_posix())
    except ValueError:return str(resolved.as_posix())


def docker_engine_available():
    try:
        outcome = subprocess.run(['docker','version','--format','{{.Server.Version}}'],capture_output=True,text=True)
    except FileNotFoundError:
        return False
    return outcome.returncode==0


def run_name_for(episode,task):
    density = int(round(float(task['density_per_m2'])*1000))
    return 'primary_%s_%s_v%d_s%02d_t%02d'%(episode['model'],task['condition'],density,
                                            int(round(episode['speed_mps'])),int(task['trial']))


def select_episodes(protocol,methods=None,condition=None,speeds=None,episode_id=None,limit=0,paper_first10=False):
    selected = []
    for episode in protocol['episodes']:
        task = protocol['tasks'][episode['task_index']]
        if episode_id and episode['id']!=episode_id:continue
        if paper_first10 and not episode.get('paper_first10'):continue
        if methods and episode['model'] not in methods:continue
        if condition and task['condition']!=condition:continue
        if speeds and int(round(episode['speed_mps'])) not in speeds:continue
        selected.append((episode,task))
        if limit and len(selected)>=limit:break
    return selected


def projected_wall_seconds(protocol,pairs):
    """Projection from one measured reference flight plus a fixed start-up term."""
    rt = REFERENCE_FLIGHT['real_time_factor']
    total = 0.
    for episode,task in pairs:
        sim = float(task['straight_distance_m'])/max(float(episode['speed_mps']),1e-6)+3.
        total += STARTUP_OVERHEAD_S+sim/max(rt,1e-3)
    return total


def load_progress(path):
    if not Path(path).is_file():return {'version':1,'episodes':{}}
    return json.loads(Path(path).read_text(encoding='utf-8'))


def terminal_record(progress,episode_id):
    record = progress['episodes'].get(episode_id)
    if not record:return None
    return record if record.get('status') in TERMINAL else None


def admission_episodes(path):
    if not Path(path).is_file():return {}
    record = json.loads(Path(path).read_text(encoding='utf-8'))
    consumed = {}
    for episode_id in record.get('consumed_episode_ids',[]):
        evidence = (record.get('phase_b',{}).get(episode_id) or {}).get('evidence',{})
        consumed[episode_id] = {'status':evidence.get('status'),'run':(record.get('phase_b',{}).get(episode_id) or {}).get('run'),
                                'source':'runtime_validation_phase_b','evidence':evidence}
    return consumed


def read_flight_summary(folder):
    metrics_path = folder/'metrics.json'
    if not metrics_path.is_file():return None
    metrics = json.loads(metrics_path.read_text(encoding='utf-8'))
    validation_path = folder/'validation.json';evaluation_path = folder/'evaluation.json'
    summary = {'status':metrics.get('status'),'scope':metrics.get('scope'),
               'sim_duration_s':metrics.get('sim_duration_s'),'wall_runtime_s':metrics.get('wall_runtime_s'),
               'real_time_factor':metrics.get('real_time_factor'),'frames':metrics.get('frames'),
               'path_length_m':metrics.get('path_length_m'),'min_net_clearance_m':metrics.get('min_net_clearance_m'),
               'goal_error_m':metrics.get('goal_error_m'),'buffer_stats':metrics.get('buffer_stats'),
               'checkpoint_sha256':metrics.get('checkpoint_sha256'),
               'metrics_path':display_path(metrics_path),'metrics_sha256':sha256_file(metrics_path)}
    for name,path in [('validation',validation_path),('evaluation',evaluation_path)]:
        if path.is_file():
            summary[name+'_path'] = display_path(path)
            summary[name+'_sha256'] = sha256_file(path)
            try:
                payload = json.loads(path.read_text(encoding='utf-8'))
                if name=='validation':summary['validation_status'] = payload.get('status')
                else:summary['evaluation_metrics_available'] = payload.get('metrics_available')
            except Exception as exc:
                summary[name+'_parse_error'] = str(exc)
    summary['traceback_present'] = bool(metrics.get('traceback'))
    return summary


def evidence_problems(flight_status,summary,evidence_checks,driver_status):
    """Mirror the aggregator's own evidence rule for each terminal outcome.

    A crash is a legitimate, reportable failure in the frozen protocol, so it
    must NOT be retried into a success: it is accepted when it carries the
    diagnostic traceback the aggregator requires. Everything else must pass the
    validator, the evaluator and the metric-availability gate.
    """
    problems = []
    if driver_status!='completed':problems.append('runner/driver status: %s'%driver_status)
    if flight_status not in TERMINAL:problems.append('flight status %s is not terminal'%flight_status)
    if evidence_checks.get('evaluate_returncode')!=0:
        problems.append('evaluate returncode %s'%evidence_checks.get('evaluate_returncode'))
    if flight_status=='crashed':
        if not summary.get('traceback_present'):problems.append('crash lacks diagnostic traceback evidence')
    else:
        if evidence_checks.get('validate_returncode')!=0:
            problems.append('validate returncode %s'%evidence_checks.get('validate_returncode'))
        if summary.get('validation_status')!='passed':
            problems.append('validation status %s'%summary.get('validation_status'))
        if summary.get('evaluation_metrics_available') is not True:
            problems.append('flight metrics unavailable')
    return problems


def choose_run_name(episode,task,progress,root=None):
    """First free run name for this episode; never reuse an existing folder."""
    root = Path(root or ROOT)
    base = run_name_for(episode,task)
    used = {entry['run'] for entry in progress.get('attempts',{}).get(episode['id'],[])}
    for index in range(1,4):
        candidate = base if index==1 else '%s_r%d'%(base,index)
        if candidate in used:continue
        if not (root/'artifacts/ros2_flights'/candidate).exists():return candidate,index
    return None,None


def quarantine_run(run_name,reason,root=None):
    """Move rejected evidence out of the primary scan path, preserving all files."""
    root = Path(root or ROOT)
    source = root/'artifacts/ros2_flights'/run_name
    if not source.exists():return None
    destination = root/'artifacts/ros2_flights_quarantine'/run_name
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():raise RuntimeError('Quarantine destination already exists: %s'%destination)
    source.rename(destination)
    manifest = {'run':run_name,'reason':reason,'moved_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                'moved_from':str(source.relative_to(root).as_posix()),
                'moved_to':str(destination.relative_to(root).as_posix()),
                'files':{p.name:sha256_file(p) for p in sorted(destination.glob('*')) if p.is_file()},
                'note':'Rejected evidence is preserved here and excluded from the primary aggregation scan; '
                       'the episode is retried under a new run name.'}
    write_json_atomic(destination/'quarantine.json',manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--protocol',type=Path,default=ROOT/'benchmarks/protocol_v1/protocol.json')
    parser.add_argument('--methods',help='comma separated model names')
    parser.add_argument('--condition',choices=['sparse','dense'])
    parser.add_argument('--speeds',help='comma separated speeds in m/s')
    parser.add_argument('--episode-id')
    parser.add_argument('--limit',type=int,default=0)
    parser.add_argument('--paper-first10',action='store_true',
                        help='Restrict the batch to the paper-size first-10 subset of the frozen matrix')
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--progress',type=Path,default=ROOT/'artifacts/benchmark_summary/matrix_progress.json')
    parser.add_argument('--plan',type=Path,default=ROOT/'artifacts/benchmark_summary/plan.json')
    parser.add_argument('--result',type=Path,default=ROOT/'artifacts/benchmark_summary/matrix_result.json')
    parser.add_argument('--driver-timeout-s',type=float,default=0.,
                        help='Override the per-episode wall-clock guard (default derived from the task timeout)')
    parser.add_argument('--max-consecutive-failures',type=int,default=3,
                        help='Stop the batch when this many episodes in a row fail their evidence gates')
    args = parser.parse_args()
    protocol_path = args.protocol.resolve()
    protocol,protocol_sha = load_protocol(protocol_path)
    methods = {v.strip() for v in args.methods.split(',')} if args.methods else None
    speeds = {int(v) for v in args.speeds.split(',')} if args.speeds else None
    pairs = select_episodes(protocol,methods,args.condition,speeds,args.episode_id,args.limit,args.paper_first10)
    ids = [episode['id'] for episode,_ in pairs]
    if len(set(ids))!=len(ids):raise ValueError('Protocol contains duplicate episode ids in the selection')
    progress = load_progress(args.progress)
    consumed = admission_episodes(protocol_path.parent/'runtime_validation.json')
    done = [episode['id'] for episode,_ in pairs if terminal_record(progress,episode['id']) or episode['id'] in consumed]
    pending = [(episode,task) for episode,task in pairs if episode['id'] not in set(done)]
    by_method = {}
    for episode,_ in pairs:by_method[episode['model']] = by_method.get(episode['model'],0)+1
    projection = projected_wall_seconds(protocol,pending)
    plan = {'version':1,'mode':'execute' if args.execute else 'dry_run','recorded_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
            'protocol':display_path(protocol_path),'protocol_sha256':protocol_sha,
            'selected_episodes':len(pairs),'already_terminal':len(done),'pending_episodes':len(pending),
            'paper_first10_only':bool(args.paper_first10),
            'selected_by_method':by_method,'pending_by_method':{m:sum(1 for e,_ in pending if e['model']==m) for m in sorted(by_method)},
            'pending_ids':[episode['id'] for episode,_ in pending],
            'consumed_by_runtime_admission':sorted(consumed),
            'projection':{'basis':'one measured reference flight (%s) plus %.0fs fixed start-up per episode'%(
                              REFERENCE_FLIGHT['source'],STARTUP_OVERHEAD_S),
                          'startup_overhead_evidence':STARTUP_OVERHEAD_EVIDENCE,
                          'reference_flight':REFERENCE_FLIGHT,'startup_overhead_s':STARTUP_OVERHEAD_S,
                          'projected_serial_wall_hours':projection/3600.,
                          'caveat':'projection only; it is not a measurement of the matrix'},
            'execution_rules':['one Isaac process at a time','skip episodes with terminal evidence or runtime-admission evidence',
                               'never overwrite primary evidence','wall-clock guard kills a hung episode and records it as a driver timeout'],
            'runtime_validation_present':(protocol_path.parent/'runtime_validation.json').is_file()}
    write_json_atomic(args.plan,plan)
    print(json.dumps({k:v for k,v in plan.items() if k not in ('pending_ids','runtime_validation_present')},indent=2,ensure_ascii=False)[:1800])
    if not args.execute:return
    admission_path = protocol_path.parent/'runtime_validation.json'
    if not admission_path.is_file():raise SystemExit('Runtime admission record is missing; run scripts/record_runtime_validation.py first')
    admission = json.loads(admission_path.read_text(encoding='utf-8'))
    if admission.get('status')!='passed' or admission.get('protocol_sha256')!=protocol_sha:
        raise SystemExit('Runtime admission record does not match this frozen protocol')
    require_training_gpu_released()
    progress.setdefault('episodes',{})
    progress['protocol_sha256'] = protocol_sha
    progress['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
    write_json_atomic(args.progress,progress)
    failures = []
    consecutive_failures = 0
    stop_reason = None
    def note_skip(episode,task,status,problem):
        progress.setdefault('episodes',{})[episode['id']] = {'episode_id':episode['id'],
            'run':run_name_for(episode,task),'model':episode['model'],'condition':task['condition'],
            'speed_mps':episode['speed_mps'],'driver_status':'skipped','status':status,
            'problem':problem,'recorded_at':time.strftime('%Y-%m-%dT%H:%M:%S%z')}
        progress['protocol_sha256'] = protocol_sha
        progress['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        write_json_atomic(args.progress,progress)
        failures.append({'episode_id':episode['id'],'problem':problem})
    for index,(episode,task) in enumerate(pending,1):
        if not docker_engine_available():
            stop_reason = 'engine_unavailable'
            write_json_atomic(args.result,{'version':1,'status':'batch_stopped_engine_unavailable',
                'attempted':index-1,'pending_after_stop':len(pending)-(index-1),'failures':failures,
                'stopped_at':time.strftime('%Y-%m-%dT%H:%M:%S%z')})
            print('MATRIX_STOPPED engine unavailable before episode %s'%episode['id'],flush=True)
            break
        episode_id = episode['id']
        mission = resolve_episode(protocol_path,episode_id)
        if mission['backend']=='mppi_reference17':
            note_skip(episode,task,'not_attempted_backend_unavailable',
                      'mppi_reference17 has no validated native adapter; not substituted')
            continue
        if mission['backend'] not in admission.get('validated_backends',[]):
            note_skip(episode,task,'not_attempted_backend_unvalidated',
                      'backend %s is not in the runtime admission record'%mission['backend'])
            continue
        run_name,attempt = choose_run_name(episode,task,progress)
        if run_name is None:
            note_skip(episode,task,'not_attempted_attempts_exhausted',
                      'three run names already used for this episode; inspect the quarantined evidence')
            continue
        folder = ROOT/'artifacts/ros2_flights'/run_name
        guard = args.driver_timeout_s or max(900.,float(episode['timeout_s'])*6.)
        log = ROOT/'artifacts/benchmark_summary'/(run_name+'.log')
        device = 'cuda' if mission['backend'] in ('yopo','yopo_reference','agile') else 'cpu'
        command = [ISAAC_PYTHON,str(ROOT/'scripts/run_ros2_navigation.py'),'--run',run_name,
                   '--episode-id',episode_id,'--protocol',str(protocol_path),'--device',device]
        env = os.environ.copy();env['OMNI_KIT_ACCEPT_EULA'] = 'YES'
        started = time.perf_counter();status = 'driver_error'
        try:
            with log.open('a',encoding='utf-8') as handle:
                completed = subprocess.run(command,cwd=ROOT,env=env,stdout=handle,stderr=subprocess.STDOUT,timeout=guard)
            status = 'completed' if completed.returncode==0 else 'runner_exit_%d'%completed.returncode
        except subprocess.TimeoutExpired:
            status = 'driver_timeout'
        finally:
            wall = time.perf_counter()-started
        if status!='completed':
            subprocess.run(['docker','rm','-f','yopo-flight-'+run_name.lower()],cwd=ROOT,capture_output=True)
        evidence_checks = {}
        for name,script in [('validate','scripts/validate_ros2_flight.py'),('evaluate','scripts/evaluate_ros2_flight.py')]:
            outcome = subprocess.run([ISAAC_PYTHON,str(ROOT/script),'--run',run_name],cwd=ROOT,capture_output=True,text=True)
            (ROOT/'artifacts/benchmark_summary'/(run_name+'_'+name+'.log')).write_text(outcome.stdout+outcome.stderr,encoding='utf-8')
            evidence_checks[name+'_returncode'] = int(outcome.returncode)
        summary = read_flight_summary(folder) or {}
        problems = evidence_problems(summary.get('status'),summary,evidence_checks,status)
        accepted = not problems
        record = {'episode_id':episode_id,'run':run_name,'attempt':attempt,'model':episode['model'],
                  'condition':task['condition'],'speed_mps':episode['speed_mps'],'driver_status':status,
                  'evidence_status':'accepted' if accepted else 'rejected',
                  'status':summary.get('status') if accepted else 'invalid_evidence',
                  'evidence_checks':evidence_checks,'evidence_problems':problems,
                  'wall_s':wall,'recorded_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'summary':summary}
        if not accepted:
            manifest = quarantine_run(run_name,'; '.join(problems))
            record['quarantined'] = manifest is not None
            if manifest:record['quarantine_manifest'] = manifest['moved_to']+'/quarantine.json'
            failures.append({'episode_id':episode_id,'run':run_name,'kind':'evidence_rejected','problems':problems})
            consecutive_failures += 1
        else:consecutive_failures = 0
        progress.setdefault('attempts',{}).setdefault(episode_id,[]).append(
            {'run':run_name,'accepted':accepted,'problems':problems,'recorded_at':record['recorded_at']})
        progress.setdefault('episodes',{})[episode_id] = record
        progress['protocol_sha256'] = protocol_sha
        progress['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        write_json_atomic(args.progress,progress)
        print('MATRIX %d/%d %s %s wall=%.0fs'%(index,len(pending),episode_id,record['status'],wall),flush=True)
        if consecutive_failures>=max(1,args.max_consecutive_failures):
            stop_reason = 'consecutive_failures'
            write_json_atomic(args.result,{'version':1,'status':'batch_stopped_consecutive_failures',
                'attempted':index,'pending_after_stop':len(pending)-index,'failures':failures,
                'stopped_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                'note':'Stopped to protect the retry budget; inspect the quarantined evidence before re-running.'})
            print('MATRIX_STOPPED %d consecutive evidence failures'%consecutive_failures,flush=True)
            break
    if stop_reason is None:
        write_json_atomic(args.result,
                          {'version':1,'status':'batch_finished','attempted':len(pending),'failures':failures,
                           'finished_at':time.strftime('%Y-%m-%dT%H:%M:%S%z')})
    print(json.dumps({'attempted':len(pending),'failures':len(failures)},indent=2))
    if failures:raise SystemExit('%d episodes did not produce terminal evidence'%len(failures))


if __name__=='__main__':main()
