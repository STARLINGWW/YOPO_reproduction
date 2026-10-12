"""CPU-only tests for the native runtime admission gate (no GPU, no Isaac)."""
from pathlib import Path
import json
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))
import record_runtime_validation as admission


def make_run(root,name,status='success',applied=120,frames=200,interface=True,validation='passed',
             evaluation=True,planner_stats=None):
    folder = Path(root)/'artifacts/ros2_flights'/name
    folder.mkdir(parents=True,exist_ok=True)
    metrics = {'status':status,'interface_passed':interface,'frames':frames,'buffer_stats':{'applied':applied},
               'max_speed_mps':1.2,'min_net_clearance_m':0.9,'real_time_factor':0.43,'goal_error_m':0.1}
    (folder/'metrics.json').write_text(json.dumps(metrics),encoding='utf-8')
    if validation:
        (folder/'validation.json').write_text(json.dumps({'status':validation}),encoding='utf-8')
    if evaluation:
        (folder/'evaluation.json').write_text(json.dumps({'metrics_available':True,'instrumentation_gaps':[]}),encoding='utf-8')
    if planner_stats is not None:
        (folder/'planner_status.json').write_text(json.dumps({'stats':planner_stats}),encoding='utf-8')
    return folder


def test_accepts_a_healthy_run(tmp_path):
    make_run(tmp_path,'rv_ok',planner_stats={'planner_errors':0,'wrong_episode':0,'stale_result':0})
    evidence = admission.verify_run('rv_ok','yopo_seed0',root=tmp_path)
    assert evidence['status']=='success' and evidence['applied_trajectories']==120
    assert evidence['validation_status']=='passed' and evidence['metrics_available'] is True
    assert evidence['problems']==[]


@pytest.mark.parametrize('kwargs,match',[
    ({'status':'crashed'},'flight status'),
    ({'applied':2},'applied trajectories below 3'),
    ({'interface':False},'interface_passed'),
    ({'frames':0},'no depth frames'),
    ({'validation':'failed'},'independent validation status failed'),
    ({'validation':None},'missing independent validation.json'),
    ({'evaluation':False},'missing evaluation.json'),
    ({'planner_stats':{'planner_errors':1,'wrong_episode':0,'stale_result':0}},'planner errors reported'),
    ({'planner_stats':{'planner_errors':0,'wrong_episode':3,'stale_result':0}},'wrong-episode responses'),
    ({'planner_stats':{'planner_errors':0,'wrong_episode':0,'stale_result':2}},'stale results reported'),
])
def test_rejects_bad_evidence(tmp_path,kwargs,match):
    make_run(tmp_path,'rv_bad',**kwargs)
    with pytest.raises(RuntimeError,match=match):
        admission.verify_run('rv_bad','yopo_seed0',root=tmp_path)


def test_missing_metrics_is_an_error(tmp_path):
    with pytest.raises(RuntimeError,match='Missing flight metrics'):
        admission.verify_run('does_not_exist','yopo_seed0',root=tmp_path)


def test_runtime_file_list_is_complete():
    missing = [name for name in admission.RUNTIME_FILES if not (ROOT/name).is_file()]
    assert missing==[]


def test_admission_backends_map_to_real_runner_backends():
    assert admission.BACKENDS['yopo_seed0']['backend']=='yopo'
    assert admission.BACKENDS['agile_autonomy']['backend']=='agile'
    assert admission.BACKENDS['topotraj']['backend']=='topotraj'
    assert admission.BACKENDS['topotraj']['device']=='cpu'
    assert admission.BACKENDS['yopo_seed0']['checkpoint'].endswith('best_policy.pth')
