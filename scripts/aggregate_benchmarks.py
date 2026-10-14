"""Collect primary run evidence; diagnostic videos never fill benchmark slots."""
from pathlib import Path
import argparse,hashlib,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from yopo_eval.aggregate import aggregate,TERMINAL
from yopo_eval.task_spec import resolve_episode,verify_formal_yopo_checkpoint
parser=argparse.ArgumentParser();parser.add_argument('--protocol',type=Path,default=ROOT/'benchmarks/protocol_v1/protocol.json')
parser.add_argument('--scope',type=Path,default=ROOT/'benchmarks/protocol_v1/active_scope_yopo_only.json')
parser.add_argument('--superset',action='store_true',help='Aggregate the full frozen superset protocol instead of the active YOPO-only scope')
parser.add_argument('--allow-regression',action='store_true',
    help='Allow overwriting an existing summary.json with fewer completed episodes (refused by default: '
         'an emptied or relocated run store must not silently degrade the frozen summary)')
args=parser.parse_args()
protocol_path=args.protocol.resolve();protocol=json.loads(protocol_path.read_text());digest=hashlib.sha256(protocol_path.read_bytes()).hexdigest()
scope=None;active_protocol=protocol
if not args.superset:
    scope=json.loads(args.scope.resolve().read_text())
    active_models=set(scope['active_models'])
    active_episodes=[episode for episode in protocol['episodes'] if episode['model'] in active_models]
    if len(active_episodes)!=scope['expected_episodes']:
        raise SystemExit('Active scope expects %d episodes but the protocol provides %d'%(scope['expected_episodes'],len(active_episodes)))
    active_protocol={**protocol,'episodes':active_episodes}
records={};duplicates=[];invalid=[];ignored=[];measurement_gaps=[]
for path in sorted((ROOT/'artifacts/ros2_flights').glob('*/metrics.json')):
    source=json.loads(path.read_text());mission=source.get('mission')
    if source.get('scope')!='primary_frozen_benchmark' or not mission:
        ignored.append(path.parent.name);continue
    identity=mission.get('episode_id');folder=path.parent
    try:
        resolved=resolve_episode(protocol_path,identity)
        assert mission['protocol_sha256']==digest and mission['episode']==resolved['episode']
        assert json.loads((folder/'scene.json').read_text())==resolved['scene']
        assert source['backend']==resolved['backend'] and source['status'] in TERMINAL
        admission=source.get('runtime_admission') or {}
        assert admission.get('status')=='passed' and admission.get('protocol_sha256')==digest
        assert source['backend'] in admission.get('validated_backends',[])
        if resolved['backend']=='yopo':
            audit=verify_formal_yopo_checkpoint(ROOT,ROOT/'checkpoints'/source['config']['checkpoint'],resolved['training_seed'])
            assert source['checkpoint_sha256']==audit['selection']['best_policy_file_sha256']
        elif resolved['backend']=='agile':
            exported=json.loads((ROOT/'artifacts/agile_autonomy/torch_export_v1/manifest.json').read_text())
            assert source['checkpoint_sha256']==exported['source_checkpoint_sha256']
        if source['status']=='crashed':
            assert source.get('traceback'),'Crash lacks diagnostic evidence'
        else:
            validation=json.loads((folder/'validation.json').read_text())
            assert validation['status']=='passed'
            assert validation['flight_sha256']==hashlib.sha256((folder/'flight.npz').read_bytes()).hexdigest()
            assert validation['checkpoint_sha256']==source['checkpoint_sha256']
            assert validation['identity_sha256']==source['identity_sha256']
        evaluation=json.loads((folder/'evaluation.json').read_text()) if (folder/'evaluation.json').is_file() else {}
        assert evaluation.get('checkpoint_sha256',source['checkpoint_sha256'])==source['checkpoint_sha256']
        if not evaluation or evaluation.get('instrumentation_gaps') or not evaluation.get('metrics_available',True):
            measurement_gaps.append({'episode_id':identity,'run':folder.name,'gaps':evaluation.get('instrumentation_gaps',['evaluation not available'])})
        samples=[]
        if (folder/'flight.npz').is_file():
            with np.load(folder/'flight.npz') as data:
                if data['latencies'].size:samples=(data['latencies'][:,2]*1000).tolist()
        if identity in records:
            duplicates.append({'episode_id':identity,'runs':[records[identity]['run'],folder.name]});continue
        records[identity]={'status':source['status'],'run':folder.name,'metrics':evaluation,'latency_samples_ms':samples}
    except Exception as exc:invalid.append({'run':folder.name,'episode_id':identity,'error':repr(exc)})
for duplicate in duplicates:records.pop(duplicate['episode_id'],None)
extra=set(records)-{episode['id'] for episode in active_protocol['episodes']}
if extra:raise SystemExit('Records outside the active scope: %s'%sorted(extra)[:5])
report=aggregate(active_protocol,records);report.update(protocol_sha256=digest,ignored_diagnostic_runs=ignored,
    duplicate_primary_attempts=duplicates,invalid_evidence=invalid,measurement_gaps=measurement_gaps)
if scope:
    report['active_scope']={'file':args.scope.resolve().relative_to(ROOT).as_posix(),'id':scope['id'],
        'models':scope['active_models'],'expected_episodes':scope['expected_episodes']}
    report['superset']={'path':'benchmarks/protocol_v1/protocol.json','label':scope['superset_protocol']['label'],
        'status':scope['superset_protocol']['status'],'expected_episodes':scope['superset_protocol']['expected_episodes'],
        'excluded_models':scope['excluded_models']}
if duplicates or invalid:report['status']='invalid_evidence'
destination=ROOT/'artifacts/benchmark_summary';destination.mkdir(exist_ok=True)
previous=None
if (destination/'summary.json').is_file():
    try:previous=json.loads((destination/'summary.json').read_text())
    except Exception:previous=None
if previous and isinstance(previous.get('completed_episodes'),int) and report['completed_episodes']<previous['completed_episodes'] and not args.allow_regression:
    raise SystemExit('Refusing to overwrite summary.json with fewer completed episodes (%d < %d). '
                     'If the run store was intentionally relocated or cleaned, re-run with --allow-regression.'
                     %(report['completed_episodes'],previous['completed_episodes']))
(destination/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='groups'}))
