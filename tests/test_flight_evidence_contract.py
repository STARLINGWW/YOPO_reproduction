"""Synthetic end-to-end check that the evaluator feeds the aggregator correctly.

No Isaac and no GPU: a synthetic but structurally real flight log is evaluated
by scripts/evaluate_ros2_flight.py (with --root pointed at a temp tree) and the
result must satisfy exactly what scripts/aggregate_benchmarks.py asserts.
"""
from pathlib import Path
import json
import subprocess
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def synthetic_run(root,name='synthetic_evaluator_run',applied=True,resources=True):
    folder = root/'artifacts/ros2_flights'/name;folder.mkdir(parents=True)
    samples = 60;dt = 0.01
    log = np.zeros((samples,30))
    t = np.arange(samples)*dt
    log[:,0] = t
    log[:,1] = np.linspace(0,5,samples);log[:,2] = 0.1*np.sin(t);log[:,3] = 2.5
    log[:,4] = 2.0;log[:,5] = 0.0;log[:,6] = 0.0
    log[:,7] = 1.0
    log[:,11:14] = log[:,1:4]+0.05
    log[:,14] = 2.0
    log[:,17] = 1.0+0.1*np.sin(t);log[:,18] = 5.0-2.0*np.linspace(0,1,samples)
    log[:,19] = 0.0;log[:,20] = 9.81
    log[:,21:24] = 0.05*np.cos(t)[:,None]
    log[:,27:30] = 0.01*np.sin(t)[:,None]
    frames = np.zeros((samples,12));frames[:,0] = t;frames[:,11] = 40.0
    latencies = np.zeros((samples,4));latencies[:,2] = 0.1
    np.savez_compressed(folder/'flight.npz',log=log,frames=frames,latencies=latencies,depths=np.zeros((1,90,160),np.float32))
    events = []
    for index in range(0,samples,10):
        events.append({'status':'published','observation_stamp_ns':int((1.0+t[index])*1e9),'planner_wall_ms':12.5,
                       'queue_wall_ms':1.5,'map_fusion_wall_ms':2.0,'map_esdf_wall_ms':3.0,
                       'debug':{'planning_wall_ms':9.0}})
    (folder/'planning_events.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in events),encoding='utf-8')
    applied_events = []
    if applied:
        applied_events = [{'event':'trajectory_applied','t':float(t[i]),'capture_t':float(t[i]-0.1),
                           'available_t':float(t[i]-0.05),'wall_latency_s':0.1} for i in range(0,samples,10)]
    metrics = {'status':'success','scope':'unit_test_synthetic_evaluator','backend':'yopo','checkpoint_sha256':'0'*64,
               'identity_sha256':'0'*64,'max_physical_contact_force_N':0.0,'real_time_factor':0.4,
               'ros_clock_origin_s':1.0,'events':applied_events,'vehicle':{'collision_envelope_radius_m':0.322}}
    (folder/'metrics.json').write_text(json.dumps(metrics),encoding='utf-8')
    if resources:
        (folder/'native_resources.jsonl').write_text(json.dumps({'wall_unix_s':1.0,'native_rss_bytes':1000,
            'gpus':[{'gpu_used_memory_MiB':100}]})+'\n',encoding='utf-8')
        (folder/'planner_resources.jsonl').write_text(json.dumps({'wall_unix_s':1.0,'process_peak_rss_kib':10})+'\n',encoding='utf-8')
    return folder


def run_evaluator(root,name):
    return subprocess.run([sys.executable,str(ROOT/'scripts/evaluate_ros2_flight.py'),'--run',name,'--root',str(root)],
                          cwd=ROOT,capture_output=True,text=True)


def test_evaluator_output_satisfies_the_aggregator_contract(tmp_path):
    synthetic_run(tmp_path)
    outcome = run_evaluator(tmp_path,'synthetic_evaluator_run')
    assert outcome.returncode==0, outcome.stderr
    report = json.loads((tmp_path/'artifacts/ros2_flights/synthetic_evaluator_run/evaluation.json').read_text(encoding='utf-8'))
    assert report['metrics_available'] is True
    assert report['instrumentation_gaps']==[]
    assert report['per_command_application_audit_available'] is True
    assert report['resource_samples_available'] is True
    assert report['path_length_m']>0 and report['max_speed_mps']==2.0
    assert report['end_to_end_wall_ms']['p50']==100.0
    assert report['map_esdf_wall_ms']['p50']==3.0 and report['map_fusion_wall_ms']['p50']==2.0
    assert report['planner_queue_wall_ms']['p50']==1.5
    assert report['negative_residual_count']>=0
    assert report['scope']=='unit_test_synthetic_evaluator'


def test_missing_instrumentation_is_reported_as_gaps_not_silence(tmp_path):
    synthetic_run(tmp_path,name='synthetic_gaps',applied=False,resources=False)
    outcome = run_evaluator(tmp_path,'synthetic_gaps')
    assert outcome.returncode==0, outcome.stderr
    report = json.loads((tmp_path/'artifacts/ros2_flights/synthetic_gaps/evaluation.json').read_text(encoding='utf-8'))
    assert report['metrics_available'] is True
    assert set(report['instrumentation_gaps'])=={'per-command application events','resource samples'}
