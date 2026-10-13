"""CPU-only tests for the frozen-matrix driver; no GPU, no Isaac, no containers."""
from pathlib import Path
import json
import shutil
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))
import run_benchmark_matrix as driver

PROTOCOL = ROOT/'benchmarks/protocol_v1/protocol.json'


def protocol():
    return json.loads(PROTOCOL.read_text(encoding='utf-8'))


def test_protocol_shapes_and_run_names_are_unique():
    data = protocol()
    episodes = data['episodes']
    ids = [episode['id'] for episode in episodes]
    assert len(ids)==len(set(ids))==1800
    per_model = {}
    for episode in episodes:per_model[episode['model']] = per_model.get(episode['model'],0)+1
    assert set(per_model)=={'yopo_seed0','yopo_seed1','yopo_seed2','topotraj','agile_autonomy','mppi_reference17'}
    assert all(count==300 for count in per_model.values())
    names = [driver.run_name_for(episode,data['tasks'][episode['task_index']]) for episode in episodes]
    assert len(names)==len(set(names))
    assert all(len(name)<=120 and name.replace('_','').isalnum() for name in names)


def test_selection_filters():
    data = protocol()
    pairs = driver.select_episodes(data,methods={'yopo_seed0'})
    assert len(pairs)==300 and all(episode['model']=='yopo_seed0' for episode,_ in pairs)
    pairs = driver.select_episodes(data,methods={'yopo_seed0'},condition='dense',speeds={4})
    assert len(pairs)==30 and all(task['condition']=='dense' and int(episode['speed_mps'])==4 for episode,task in pairs)
    pairs = driver.select_episodes(data,episode_id='yopo_seed0_sparse_v2_trial00')
    assert len(pairs)==1 and pairs[0][0]['id']=='yopo_seed0_sparse_v2_trial00'
    assert len(driver.select_episodes(data,limit=7))==7
    subset = driver.select_episodes(data,paper_first10=True)
    assert len(subset)==600
    assert all(episode['paper_first10'] for episode,_ in subset)
    assert {episode['model'] for episode,_ in subset}=={'yopo_seed0','yopo_seed1','yopo_seed2','topotraj',
                                                        'agile_autonomy','mppi_reference17'}


def test_projection_is_labelled_as_projection():
    data = protocol()
    pairs = driver.select_episodes(data,methods={'yopo_seed0'},speeds={2})
    seconds = driver.projected_wall_seconds(data,pairs)
    assert seconds>0
    plan = {'projection':{'basis':'x','caveat':'projection only'}}
    assert 'projection only' in plan['projection']['caveat']


def test_dry_run_plan_and_resume(tmp_path,monkeypatch,capsys):
    protocol_dir = tmp_path/'protocol';protocol_dir.mkdir()
    shutil.copy2(PROTOCOL,protocol_dir/'protocol.json')
    shutil.copytree(PROTOCOL.parent/'maps',protocol_dir/'maps')
    (protocol_dir/'runtime_validation.json').write_text(json.dumps({'status':'passed','protocol_sha256':'x',
        'consumed_episode_ids':['yopo_seed0_sparse_v2_trial00'],
        'phase_b':{'yopo_seed0_sparse_v2_trial00':{'run':'rv_frozen_x','evidence':{'status':'success'}}}}),encoding='utf-8')
    progress = tmp_path/'progress.json'
    progress.write_text(json.dumps({'version':1,'episodes':{'yopo_seed0_sparse_v2_trial01':{'status':'success','run':'primary_x'}}}),encoding='utf-8')
    plan_path = tmp_path/'plan.json'
    monkeypatch.setattr(sys,'argv',['run_benchmark_matrix.py','--methods','yopo_seed0','--speeds','2',
                                    '--protocol',str(protocol_dir/'protocol.json'),
                                    '--plan',str(plan_path),'--progress',str(progress),'--result',str(tmp_path/'result.json')])
    driver.main()
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    assert plan['mode']=='dry_run'
    assert plan['selected_episodes']==60
    assert plan['already_terminal']==2
    assert plan['pending_episodes']==58
    assert 'yopo_seed0_sparse_v2_trial00' in plan['consumed_by_runtime_admission']
    assert 'yopo_seed0_sparse_v2_trial00' not in plan['pending_ids']
    assert 'yopo_seed0_sparse_v2_trial01' not in plan['pending_ids']
    assert plan['projection']['projected_serial_wall_hours']>0
    assert plan['runtime_validation_present'] is True


def test_execute_requires_admission(tmp_path,monkeypatch):
    protocol_dir = tmp_path/'protocol';protocol_dir.mkdir()
    shutil.copy2(PROTOCOL,protocol_dir/'protocol.json')
    shutil.copytree(PROTOCOL.parent/'maps',protocol_dir/'maps')
    monkeypatch.setattr(sys,'argv',['run_benchmark_matrix.py','--methods','yopo_seed0','--limit','1','--execute',
                                    '--plan',str(tmp_path/'plan.json'),'--progress',str(tmp_path/'progress.json'),
                                    '--result',str(tmp_path/'result.json'),
                                    '--protocol',str(protocol_dir/'protocol.json')])
    with pytest.raises(SystemExit,match='Runtime admission record is missing'):
        driver.main()


def test_execute_skips_backends_outside_admission(tmp_path,monkeypatch):
    protocol_dir = tmp_path/'protocol'
    protocol_dir.mkdir()
    shutil.copy2(PROTOCOL,protocol_dir/'protocol.json')
    shutil.copytree(PROTOCOL.parent/'maps',protocol_dir/'maps')
    (protocol_dir/'runtime_validation.json').write_text(json.dumps({'status':'passed',
        'protocol_sha256':driver.load_protocol(PROTOCOL)[1],'validated_backends':[],
        'consumed_episode_ids':[],'phase_b':{}}),encoding='utf-8')
    monkeypatch.setattr(sys,'argv',['run_benchmark_matrix.py','--methods','yopo_seed0','--limit','2','--execute',
                                    '--protocol',str(protocol_dir/'protocol.json'),
                                    '--plan',str(tmp_path/'plan.json'),'--progress',str(tmp_path/'progress.json'),
                                    '--result',str(tmp_path/'result.json')])
    monkeypatch.setattr(driver,'require_training_gpu_released',lambda:None)
    monkeypatch.setattr(driver,'docker_engine_available',lambda:True)
    flights = ROOT/'artifacts/ros2_flights'
    before = {p.name for p in flights.glob('primary_yopo_seed0_*')} if flights.is_dir() else set()
    with pytest.raises(SystemExit,match='did not produce terminal evidence'):
        driver.main()
    progress = json.loads((tmp_path/'progress.json').read_text(encoding='utf-8'))
    assert len(progress['episodes'])==2
    assert all(record['status']=='not_attempted_backend_unvalidated' for record in progress['episodes'].values())
    assert all(record['driver_status']=='skipped' for record in progress['episodes'].values())
    after = {p.name for p in flights.glob('primary_yopo_seed0_*')} if flights.is_dir() else set()
    assert after==before


def test_execute_stops_when_the_engine_is_unavailable(tmp_path,monkeypatch):
    protocol_dir = tmp_path/'protocol'
    protocol_dir.mkdir()
    shutil.copy2(PROTOCOL,protocol_dir/'protocol.json')
    shutil.copytree(PROTOCOL.parent/'maps',protocol_dir/'maps')
    (protocol_dir/'runtime_validation.json').write_text(json.dumps({'status':'passed',
        'protocol_sha256':driver.load_protocol(PROTOCOL)[1],'validated_backends':['yopo'],
        'consumed_episode_ids':[],'phase_b':{}}),encoding='utf-8')
    monkeypatch.setattr(sys,'argv',['run_benchmark_matrix.py','--methods','yopo_seed0','--limit','3','--execute',
                                    '--protocol',str(protocol_dir/'protocol.json'),
                                    '--plan',str(tmp_path/'plan.json'),'--progress',str(tmp_path/'progress.json'),
                                    '--result',str(tmp_path/'result.json')])
    monkeypatch.setattr(driver,'require_training_gpu_released',lambda:None)
    monkeypatch.setattr(driver,'docker_engine_available',lambda:False)
    flights = ROOT/'artifacts/ros2_flights'
    before = {p.name for p in flights.glob('primary_yopo_seed0_*')} if flights.is_dir() else set()
    driver.main()
    result = json.loads((tmp_path/'result.json').read_text(encoding='utf-8'))
    assert result['status']=='batch_stopped_engine_unavailable'
    assert result['attempted']==0 and result['pending_after_stop']==3
    progress = json.loads((tmp_path/'progress.json').read_text(encoding='utf-8'))
    assert progress['episodes']=={}
    after = {p.name for p in flights.glob('primary_yopo_seed0_*')} if flights.is_dir() else set()
    assert after==before


def test_run_name_retries_skip_used_and_existing(tmp_path):
    data = protocol()
    episode = next(e for e in data['episodes'] if e['model']=='yopo_seed0')
    task = data['tasks'][episode['task_index']]
    base = driver.run_name_for(episode,task)
    progress = {'attempts':{episode['id']:[{'run':base}]}}
    name,attempt = driver.choose_run_name(episode,task,progress,root=tmp_path)
    assert name==base+'_r2' and attempt==2
    (tmp_path/'artifacts/ros2_flights'/(base+'_r2')).mkdir(parents=True)
    name,attempt = driver.choose_run_name(episode,task,progress,root=tmp_path)
    assert name==base+'_r3' and attempt==3
    progress['attempts'][episode['id']].append({'run':base+'_r3'})
    assert driver.choose_run_name(episode,task,progress,root=tmp_path)==(None,None)


def test_quarantine_moves_rejected_evidence_without_deleting(tmp_path):
    run = 'primary_yopo_seed0_sparse_v2_s02_t00'
    folder = tmp_path/'artifacts/ros2_flights'/run
    folder.mkdir(parents=True)
    (folder/'metrics.json').write_text(json.dumps({'status':'crashed'}),encoding='utf-8')
    (folder/'flight.npz').write_bytes(b'raw-flight-bytes')
    manifest = driver.quarantine_run(run,'validate returncode 1',root=tmp_path)
    assert not folder.exists()
    moved = tmp_path/'artifacts/ros2_flights_quarantine'/run
    assert moved.is_dir() and (moved/'flight.npz').read_bytes()==b'raw-flight-bytes'
    payload = json.loads((moved/'quarantine.json').read_text(encoding='utf-8'))
    assert payload['reason']=='validate returncode 1'
    assert set(payload['files'])=={'metrics.json','flight.npz'}
    folder.mkdir(parents=True)
    (folder/'metrics.json').write_text(json.dumps({'status':'crashed'}),encoding='utf-8')
    with pytest.raises(RuntimeError,match='Quarantine destination already exists'):
        driver.quarantine_run(run,'second attempt',root=tmp_path)
    assert driver.quarantine_run('missing_run','no folder',root=tmp_path) is None


def test_flight_summary_reads_evidence_outcome(tmp_path):
    folder = tmp_path/'run'
    folder.mkdir()
    (folder/'metrics.json').write_text(json.dumps({'status':'success','frames':10}),encoding='utf-8')
    (folder/'validation.json').write_text(json.dumps({'status':'failed'}),encoding='utf-8')
    (folder/'evaluation.json').write_text(json.dumps({'metrics_available':False}),encoding='utf-8')
    summary = driver.read_flight_summary(folder)
    assert summary['validation_status']=='failed'
    assert summary['evaluation_metrics_available'] is False
    (folder/'validation.json').write_text('{not json',encoding='utf-8')
    summary = driver.read_flight_summary(folder)
    assert 'validation_parse_error' in summary


def test_crash_is_a_terminal_outcome_and_is_not_retried(tmp_path):
    """The protocol counts a crashed episode as a failure; retrying it until it
    succeeds would be selection bias, so it is accepted when it carries the
    traceback the aggregator requires."""
    folder = tmp_path/'run'
    folder.mkdir()
    (folder/'metrics.json').write_text(json.dumps({'status':'crashed','frames':4,
        'traceback':'Traceback (most recent call last): ...'}),encoding='utf-8')
    (folder/'flight.npz').write_bytes(b'partial')
    summary = driver.read_flight_summary(folder)
    assert summary['traceback_present'] is True
    problems = driver.evidence_problems('crashed',summary,{'evaluate_returncode':0},'completed')
    assert problems==[]
    # a crashed flight without diagnostics is still not acceptable
    (folder/'metrics.json').write_text(json.dumps({'status':'crashed','frames':4}),encoding='utf-8')
    summary = driver.read_flight_summary(folder)
    assert 'crash lacks diagnostic traceback evidence' in driver.evidence_problems('crashed',summary,{'evaluate_returncode':0},'completed')


def test_success_still_requires_the_full_validation_chain(tmp_path):
    folder = tmp_path/'run'
    folder.mkdir()
    (folder/'metrics.json').write_text(json.dumps({'status':'success','frames':10}),encoding='utf-8')
    summary = driver.read_flight_summary(folder)
    problems = driver.evidence_problems('success',summary,{'validate_returncode':0,'evaluate_returncode':0},'completed')
    assert any('validation status' in problem for problem in problems)
    assert any('flight metrics unavailable' in problem for problem in problems)
    assert driver.evidence_problems('success',summary|{'validation_status':'passed','evaluation_metrics_available':True},
                                    {'validate_returncode':0,'evaluate_returncode':0},'completed')==[]
    assert 'driver' in ' '.join(driver.evidence_problems('success',summary,{'evaluate_returncode':0},'driver_timeout'))
