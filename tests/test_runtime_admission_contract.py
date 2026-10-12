"""Producer/consumer contract for benchmarks/protocol_v1/runtime_validation.json.

The recorder writes the admission record; src/yopo_eval/task_spec.py consumes
it. If the two disagree, the matrix cannot start after training — so the
agreement is tested here with a stubbed native runner (no GPU, no Isaac).
"""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))
import record_runtime_validation as admission
from yopo_eval.task_spec import resolve_episode,verify_runtime_admission

PROTOCOL = ROOT/'benchmarks/protocol_v1/protocol.json'


def test_recorder_output_is_accepted_by_the_runner_contract(tmp_path,monkeypatch):
    for name in admission.RUNTIME_FILES:
        path = tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('// frozen',encoding='utf-8')
    protocol_dir = tmp_path/'benchmarks/protocol_v1';protocol_dir.mkdir(parents=True)
    shutil.copy2(PROTOCOL,protocol_dir/'protocol.json')
    shutil.copytree(PROTOCOL.parent/'maps',protocol_dir/'maps')
    monkeypatch.setattr(admission,'ROOT',tmp_path)
    monkeypatch.setattr(admission,'require_training_gpu_released',lambda:None)

    def fake_run_native(run_name,key,extra):
        folder = tmp_path/'artifacts/ros2_flights'/run_name;folder.mkdir(parents=True)
        (folder/'metrics.json').write_text(json.dumps({'status':'success','interface_passed':True,'frames':120,
            'buffer_stats':{'applied':120},'max_speed_mps':2.0,'min_net_clearance_m':1.1,'real_time_factor':0.4,
            'goal_error_m':0.05}),encoding='utf-8')
        (folder/'validation.json').write_text(json.dumps({'status':'passed'}),encoding='utf-8')
        (folder/'evaluation.json').write_text(json.dumps({'metrics_available':True,'instrumentation_gaps':[]}),encoding='utf-8')
        (folder/'planner_status.json').write_text(json.dumps({'stats':{'planner_errors':0,'wrong_episode':0,'stale_result':0}}),encoding='utf-8')
        return {'returncode':0,'validate_returncode':0,'evaluate_returncode':0,'log':'stub'}

    monkeypatch.setattr(admission,'run_native',fake_run_native)
    monkeypatch.setattr(sys,'argv',['record_runtime_validation.py','--backends','topotraj',
                                    '--protocol',str(protocol_dir/'protocol.json'),'--stamp','unit'])
    admission.main()
    record = json.loads((protocol_dir/'runtime_validation.json').read_text(encoding='utf-8'))
    assert record['status']=='passed'
    assert record['provisional'] is False
    assert record['validated_backends']==['topotraj']
    assert len(record['consumed_episode_ids'])==2
    assert set(record['runtime_files'])==set(admission.RUNTIME_FILES)
    assert all(len(digest)==64 for digest in record['runtime_files'].values())
    assert record['phase_a']['topotraj']['evidence']['problems']==[]

    mission = resolve_episode(protocol_dir/'protocol.json',record['consumed_episode_ids'][0])
    admission_seen = verify_runtime_admission(tmp_path,protocol_dir/'protocol.json',mission)
    assert admission_seen['status']=='passed'

    (tmp_path/'scripts/run_ros2_navigation.py').write_text('// changed after validation',encoding='utf-8')
    with pytest.raises(ValueError,match='Runtime changed after benchmark validation'):
        verify_runtime_admission(tmp_path,protocol_dir/'protocol.json',mission)

    record['validated_backends'] = []
    (protocol_dir/'runtime_validation.json').write_text(json.dumps(record),encoding='utf-8')
    with pytest.raises(ValueError,match='has not passed native runtime validation'):
        verify_runtime_admission(tmp_path,protocol_dir/'protocol.json',mission)


def _prepare(tmp_path,monkeypatch):
    for name in admission.RUNTIME_FILES:
        path = tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('// frozen',encoding='utf-8')
    protocol_dir = tmp_path/'benchmarks/protocol_v1';protocol_dir.mkdir(parents=True)
    shutil.copy2(PROTOCOL,protocol_dir/'protocol.json')
    shutil.copytree(PROTOCOL.parent/'maps',protocol_dir/'maps')
    monkeypatch.setattr(admission,'ROOT',tmp_path)
    monkeypatch.setattr(admission,'require_training_gpu_released',lambda:None)

    def fake_run_native(run_name,key,extra):
        folder = tmp_path/'artifacts/ros2_flights'/run_name;folder.mkdir(parents=True)
        (folder/'metrics.json').write_text(json.dumps({'status':'success','interface_passed':True,'frames':120,
            'buffer_stats':{'applied':120},'max_speed_mps':2.0,'min_net_clearance_m':1.1,'real_time_factor':0.4,
            'goal_error_m':0.05}),encoding='utf-8')
        (folder/'validation.json').write_text(json.dumps({'status':'passed'}),encoding='utf-8')
        (folder/'evaluation.json').write_text(json.dumps({'metrics_available':True,'instrumentation_gaps':[]}),encoding='utf-8')
        (folder/'planner_status.json').write_text(json.dumps({'stats':{'planner_errors':0,'wrong_episode':0,'stale_result':0}}),encoding='utf-8')
        return {'returncode':0,'validate_returncode':0,'evaluate_returncode':0,'log':'stub'}

    monkeypatch.setattr(admission,'run_native',fake_run_native)
    return protocol_dir


def test_validated_backends_use_protocol_backend_names_not_admission_keys(tmp_path,monkeypatch):
    """Regression: the admission keys differ from the mission backend names.

    yopo_seed0/agile_autonomy are admission keys; the frozen protocol, the
    matrix driver's skip predicate, verify_runtime_admission and the aggregator
    all address those baselines as 'yopo' and 'agile'. Before the fix the
    recorder published the keys, so every yopo and agile episode would have been
    recorded as not_attempted_backend_unvalidated (1200 of 1500 runnable slots).
    """
    protocol_dir = _prepare(tmp_path,monkeypatch)
    # The yopo admission key also exercises expected_checkpoint(), which the
    # topotraj-only test could never reach; give it a real audited checkpoint.
    seed_dir = tmp_path/'checkpoints/formal_main_v1_seed0';seed_dir.mkdir(parents=True)
    weights = b'unit-test-weight'
    (seed_dir/'best_policy.pth').write_bytes(weights)
    (seed_dir/'training_audit.json').write_text(json.dumps({'status':'passed','epochs':50,
        'selection':{'best_policy_file_sha256':hashlib.sha256(weights).hexdigest()}}),encoding='utf-8')
    monkeypatch.setattr(sys,'argv',['record_runtime_validation.py','--backends','yopo_seed0,agile_autonomy',
                                    '--protocol',str(protocol_dir/'protocol.json'),'--stamp','names'])
    admission.main()
    record = json.loads((protocol_dir/'runtime_validation.json').read_text(encoding='utf-8'))
    assert record['status']=='passed'
    assert record['validated_backends']==['agile','yopo']
    assert set(record['validated_backend_keys'])=={'yopo_seed0','agile_autonomy'}
    assert not {'yopo_seed0','agile_autonomy'} & set(record['validated_backends'])
    for episode_id in record['consumed_episode_ids']:
        mission = resolve_episode(protocol_dir/'protocol.json',episode_id)
        assert mission['backend'] in record['validated_backends']
        assert verify_runtime_admission(tmp_path,protocol_dir/'protocol.json',mission)['status']=='passed'


def test_a_failed_backend_is_never_advertised(tmp_path,monkeypatch):
    for name in admission.RUNTIME_FILES:
        path = tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('// frozen',encoding='utf-8')
    protocol_dir = tmp_path/'benchmarks/protocol_v1';protocol_dir.mkdir(parents=True)
    shutil.copy2(PROTOCOL,protocol_dir/'protocol.json')
    shutil.copytree(PROTOCOL.parent/'maps',protocol_dir/'maps')
    monkeypatch.setattr(admission,'ROOT',tmp_path)
    monkeypatch.setattr(admission,'require_training_gpu_released',lambda:None)

    def unhealthy(run_name,key,extra):
        folder = tmp_path/'artifacts/ros2_flights'/run_name;folder.mkdir(parents=True)
        (folder/'metrics.json').write_text(json.dumps({'status':'crashed','interface_passed':False,'frames':0,
            'buffer_stats':{'applied':0}}),encoding='utf-8')
        return {'returncode':1,'validate_returncode':1,'evaluate_returncode':1,'log':'stub'}

    monkeypatch.setattr(admission,'run_native',unhealthy)
    monkeypatch.setattr(sys,'argv',['record_runtime_validation.py','--backends','topotraj','--phase','a',
                                    '--protocol',str(protocol_dir/'protocol.json'),'--stamp','unit'])
    with pytest.raises(SystemExit):
        admission.main()
    record = json.loads((protocol_dir/'runtime_validation.json').read_text(encoding='utf-8'))
    assert record['status']=='failed'
    assert record['validated_backends']==[]
    assert record['phase_a']['topotraj']['problems']
    with pytest.raises(ValueError,match='Runtime validation does not match'):
        verify_runtime_admission(tmp_path,protocol_dir/'protocol.json',
                                 resolve_episode(protocol_dir/'protocol.json','topotraj_sparse_v2_trial00'))


def test_pipeline_produces_the_agile_cuda_gate_before_admission():
    """The runner refuses agile episodes without torch_cuda_parity.json, so the
    admission stage must create that evidence before it records admission."""
    text = (ROOT/'scripts/run_post_training_pipeline.ps1').read_text(encoding='utf-8')
    start = text.index("requested -contains 'admission'")
    end = text.index("requested -contains 'matrix'")
    stage = text[start:end]
    assert 'torch_cuda_parity.json' in stage
    assert 'probe_agile_torch.py --device cuda' in stage
    assert stage.index('probe_agile_torch.py') < stage.index('record_runtime_validation.py')
    assert 'Agile CUDA parity failed' in stage
