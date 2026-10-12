"""Read-back provenance, pose/depth geometry and real-flight metric checks."""
from pathlib import Path
import argparse,hashlib,json,sys
import numpy as np
from scipy.spatial.transform import Rotation
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from depth_quality import assess_depth
from yopo_sim.evaluation_geometry import ForestEvaluator
parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);args=parser.parse_args()
source=(ROOT/'artifacts/ros2_flights'/args.run).resolve()
if not source.is_relative_to(ROOT/'artifacts/ros2_flights'):raise ValueError('Unexpected flight path')
metrics=json.loads((source/'metrics.json').read_text());scene=json.loads((source/'scene.json').read_text())
planner=json.loads((source/'planner_status.json').read_text());data=np.load(source/'flight.npz')
log=data['log'];frames=data['frames'];depths=data['depths'];latency=data['latencies']
backend=metrics.get('backend','yopo');training_seed=None
if backend=='yopo':
    checkpoint=ROOT/'checkpoints'/metrics['config']['checkpoint'];manifest=json.loads((checkpoint.parent/'run_manifest.json').read_text())
    assert manifest['initialization'].startswith('random entire network')
    digest=hashlib.sha256(checkpoint.read_bytes()).hexdigest();checkpoint_name=checkpoint.name;training_seed=manifest['seed']
elif backend=='agile':
    exported=json.loads((ROOT/'artifacts/agile_autonomy/torch_export_v1/manifest.json').read_text())
    digest=exported['source_checkpoint_sha256'];checkpoint_name='official_agile_ckpt50_converted'
elif backend=='topotraj':
    digest=None;checkpoint_name=None
    identity=hashlib.sha256((source/'backend_config.yaml').read_bytes()+str(float(metrics['config']['speed'])).encode()+b'41be219fe4ecc43bf0e0c2b42a523f8755ccc0bd').hexdigest()
    assert identity==metrics['identity_sha256']==planner['identity_sha256']
else:raise ValueError('Unverified planner identity')
assert digest==metrics['checkpoint_sha256']==planner['checkpoint_sha256']
if metrics.get('mission'):
    sys.path.insert(0,str(ROOT/'src'))
    from yopo_eval.task_spec import resolve_episode
    resolved=resolve_episode(metrics['config']['protocol'],metrics['mission']['episode_id'])
    assert resolved['protocol_sha256']==metrics['mission']['protocol_sha256'] and resolved['scene']==scene
    np.testing.assert_allclose(data['start'],resolved['task']['start'],atol=1e-12)
    np.testing.assert_allclose(data['goal'],resolved['task']['goal'],atol=1e-12)
assert log.ndim==2 and log.shape[1]==len(metrics['log_columns'])==30 and len(log)>10
assert np.isfinite(log).all() and np.all(np.diff(log[:,0])>0)
assert abs(log[-1,0]-metrics['sim_duration_s'])<1e-5
assert depths.shape==(len(frames),90,160) and depths.dtype==np.float32
assert np.isfinite(depths).all() and depths.min()>=0 and depths.max()<=20
assert np.all(np.diff(frames[:,0])>0) and np.allclose(np.linalg.norm(frames[:,4:8],axis=1),1,atol=1e-6)
evaluator=ForestEvaluator(scene);radius=metrics['vehicle']['collision_envelope_radius_m']
clear=np.array([evaluator.distance(p)-radius for p in log[:,1:4]])
np.testing.assert_allclose(clear,log[:,17],atol=1e-9)
np.testing.assert_allclose(np.linalg.norm(log[-1,1:4]-data['goal']),metrics['goal_error_m'],atol=1e-9)
assert len(latency)>0 and np.isfinite(latency).all() and np.all(latency[:,2]>=0)
rng=np.random.default_rng(817);pixels=np.column_stack([rng.integers(4,156,128),rng.integers(4,86,128)])
checks=[]
for i,row in enumerate(frames):
    matrix=Rotation.from_quat(row[4:8][[1,2,3,0]]).as_matrix();camera_position=row[1:4]+matrix@np.array([0.,0.,.1])
    check=assess_depth(depths[i],camera_position,matrix,scene,pixels,i)
    if check['status']!='passed':
        (source/'failed_dynamic_geometry.json').write_text(json.dumps(check,indent=2)+'\n')
        raise AssertionError('Dynamic depth/pose geometry mismatch')
    checks.append(check)
report={'status':'passed','scope':'Measured PhysX/ROS2 flight read-back, declared planner identity and all captured-frame sampled-ray geometry; not full benchmark completion',
    'backend':backend,'identity_sha256':metrics.get('identity_sha256',digest),
    'checkpoint_sha256':digest,'training_seed':training_seed,'checkpoint_name':checkpoint_name,
    'flight_sha256':hashlib.sha256((source/'flight.npz').read_bytes()).hexdigest(),
    'navigation_status':metrics['status'],'control_samples':len(log),'depth_frames':len(frames),'rays_per_frame':128,
    'max_raw_ray_error_m':max(v['max_m'] for v in checks),
    'subpixel_ambiguous_pixels':sum(len(v['ambiguous_pixels']) for v in checks),
    'unresolved_pixels':sum(len(v['unresolved_pixels']) for v in checks),
    'planner_errors':planner['stats']['planner_errors'],'physical_contact_max_N':metrics['max_physical_contact_force_N'],
    'per_command_application_events':sum(e['event']=='trajectory_applied' for e in metrics.get('events',[]))}
(source/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
