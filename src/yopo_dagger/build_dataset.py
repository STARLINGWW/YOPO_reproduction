"""Build a separate aggregation dataset from real closed-loop YOPO rollouts.

The formal training dataset is never modified. This builder validates every
recorded flight (camera geometry, map separation, finite frames, unit
quaternions, per-frame depth hashes, independent ray geometry QA), stages the
frames into new shards whose map backend is the original bucket SDF, and emits
a new dataset index whose valid/test shards are byte-identical to the base.

The aggregation dataset is a *fine-tuning data version*: it is the base data
plus on-policy states the trained policy actually visits. It is not expert
labelled data and it does not replace the base training dataset.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys
import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'scripts'))
from yopo_repro.io import sha256_file, write_json_atomic
from yopo_repro.maps import surface_points, write_ply, pointcloud_esdf
from yopo_repro.forest import generate, ray_depth
from depth_quality import assess_depth


CAMERA_CONFIG = {'width':160,'height':90,'fx':80.,'fy':80.,'cx_pixel_index':79.5,
                 'cy_pixel_index':44.5,'body_translation_m':[0.,0.,.1]}
RAW_SHAPE = (90,160)
MAX_DEPTH_M = 20.
FORBIDDEN_MAP_SEEDS = set(range(100,120)) | set(range(1000,1004)) | set(range(2000,2004)) | set(range(3000,3001)) | set(range(5000,6010))


def pixel_probe(seed=817,count=128):
    rng = np.random.default_rng(seed)
    return np.column_stack([rng.integers(4,156,count),rng.integers(4,86,count)])


def _rays(pixels,rotation):
    return np.column_stack([np.ones(len(pixels)),-(pixels[:,0]+.5-80)/80,-(pixels[:,1]+.5-45)/80])@rotation.T


def render_reference_frame(scene,position,quaternion,pixels=None):
    """Independent ray render used by tests and by the optional self-check."""
    rotation = Rotation.from_quat(np.asarray(quaternion,float)[[1,2,3,0]]).as_matrix()
    camera = np.asarray(position,float)+rotation@np.array(CAMERA_CONFIG['body_translation_m'])
    pixels = pixel_probe() if pixels is None else np.asarray(pixels)
    return ray_depth(camera,_rays(pixels,rotation),scene)


def validate_camera(metrics):
    camera = metrics.get('camera')
    if not isinstance(camera,dict):raise ValueError('Flight record has no camera block')
    for key,value in CAMERA_CONFIG.items():
        if key not in camera:raise ValueError('Flight camera block lacks '+key)
        if isinstance(value,list):
            if not np.allclose(np.asarray(camera[key],float),np.asarray(value,float),atol=1e-12):
                raise ValueError('Flight camera %s differs from the training convention'%key)
        elif not np.isclose(float(camera[key]),float(value),atol=1e-12):
            raise ValueError('Flight camera %s differs from the training convention'%key)
    return {k:camera[k] for k in CAMERA_CONFIG}


def read_flight(folder):
    folder = Path(folder)
    metrics = json.loads((folder/'metrics.json').read_text(encoding='utf-8'))
    scene = json.loads((folder/'scene.json').read_text(encoding='utf-8'))
    camera = validate_camera(metrics)
    data = np.load(folder/'flight.npz')
    depths = np.asarray(data['depths'],dtype=np.float32)
    frames = np.asarray(data['frames'],dtype=np.float64)
    if depths.ndim!=3 or depths.shape[1:]!=RAW_SHAPE:raise ValueError('Unexpected depth shape %s'%(depths.shape,))
    if frames.ndim!=2 or frames.shape[1]!=12:raise ValueError('Unexpected frame telemetry shape %s'%(frames.shape,))
    if len(frames)!=len(depths):raise ValueError('Depth/frame count mismatch')
    if not len(depths):raise ValueError('Empty flight record')
    if not np.isfinite(depths).all():raise ValueError('Non-finite depth')
    if depths.min()<0 or depths.max()>MAX_DEPTH_M:raise ValueError('Depth outside the stored 0-20m range')
    positions = frames[:,1:4]
    quaternions = frames[:,4:8]
    if not np.isfinite(positions).all() or not np.isfinite(quaternions).all():
        raise ValueError('Non-finite pose')
    norms = np.linalg.norm(quaternions,axis=1)
    deviation = float(np.max(np.abs(norms-1.)))
    if deviation>1e-6:raise ValueError('Recorded quaternion not unit within tolerance: %g'%deviation)
    quaternions = quaternions/norms[:,None]
    rotations = Rotation.from_quat(quaternions[:,[1,2,3,0]]).as_matrix()
    camera_positions = positions+np.einsum('bij,j->bi',rotations,np.array(CAMERA_CONFIG['body_translation_m']))
    return {'folder':str(folder.resolve()),'metrics':metrics,'scene':scene,'camera':camera,
            'depths':depths,'positions':positions,'quaternions':quaternions,
            'camera_positions':camera_positions,'quaternion_norm_deviation':deviation,
            'status':metrics.get('status'),'map_seed':int(metrics['config']['map_seed']),
            'scope':metrics.get('scope'),'checkpoint_sha256':metrics.get('checkpoint_sha256'),
            'flight_sha256':sha256_file(folder/'flight.npz'),'scene_sha256':sha256_file(folder/'scene.json'),
            'metrics_sha256':sha256_file(folder/'metrics.json')}


def resolve_flight_folders(flights_root):
    """Accept either a directory of flight folders or a driver manifest."""
    flights_root = Path(flights_root)
    manifest = flights_root/'flights.json'
    if manifest.is_file():
        data = json.loads(manifest.read_text(encoding='utf-8'))
        folders = []
        for entry in data['flights']:
            folder = Path(entry['path'])
            if not folder.is_absolute():folder = ROOT/folder
            folders.append(folder)
        return folders
    return sorted(p for p in flights_root.iterdir() if p.is_dir())


def verify_base_shards(base_index,base_root,output_root):
    """Prove the base shards still match their index and derive relative paths."""
    evidence = {};paths = {}
    for shard in base_index['shards']:
        folder = Path(base_root)/shard['path']
        relative = Path(os.path.relpath(folder,output_root)).as_posix()
        paths[str(shard['id'])] = {'index_path':shard['path'],'aggregation_path':relative}
        evidence[str(shard['id'])] = {'split':shard['split'],'map_seed':shard['map_seed'],
            'manifest_sha256':sha256_file(folder/'manifest.json'),'map_sha256':sha256_file(folder/'map.json'),
            'matches_index':sha256_file(folder/'manifest.json')==shard['manifest_sha256'] and
                            sha256_file(folder/'map.json')==shard['map_sha256']}
    if not all(v['matches_index'] for v in evidence.values()):
        raise ValueError('Base dataset shards no longer match their recorded hashes')
    shards = [{**shard,'base_path':shard['path'],'path':paths[str(shard['id'])]['aggregation_path']}
              for shard in base_index['shards']]
    return evidence,paths,shards


def docker_sdf_builder(folder,occupancy):
    """Original-main bucket SDF through the pinned reference ROS2 executable."""
    folder = Path(folder);target = folder/'sdf.f32'
    def container_path(path):
        return '/workspace/'+Path(path).resolve().relative_to(ROOT).as_posix()
    subprocess.run(['docker','compose','run','--rm','-T','ros','ros2','run','yopo_math_reference','sdf_reference',
                    '--binary',container_path(folder/'occupancy.u8'),container_path(target),
                    *[str(v) for v in occupancy.shape]],cwd=ROOT,check=True)
    values = np.fromfile(target,dtype='<f4').reshape(occupancy.shape)
    if not np.isfinite(values).all():raise RuntimeError('Non-finite reference SDF')
    return values


def build_map_assets(folder,scene,sdf_builder):
    folder = Path(folder);folder.mkdir(parents=True,exist_ok=True)
    points = surface_points(scene,.1)
    write_ply(folder/'pointcloud.ply',points)
    _,occupancy,origin,upper = pointcloud_esdf(points,.2)
    (folder/'occupancy.u8').write_bytes(occupancy.astype(np.uint8).tobytes())
    values = sdf_builder(folder,occupancy)
    if np.shape(values)!=occupancy.shape:raise ValueError('Reference SDF shape mismatch')
    if not np.isfinite(values).all():raise ValueError('Non-finite reference SDF')
    np.save(folder/'sdf.npy',values)
    write_json_atomic(folder/'map.json',{'backend':'original_main_bucket','origin':origin.tolist(),
        'upper':upper.tolist(),'resolution':.2,'shape':list(values.shape),'sdf_sha256':sha256_file(folder/'sdf.npy'),
        'pointcloud_sha256':sha256_file(folder/'pointcloud.ply')})
    return origin,upper,points


def qa_frames(depths,camera_positions,quaternions,scene,frames,seed=817,probe=128):
    if frames<=0:return []
    pixels = pixel_probe(seed,probe)
    indices = np.unique(np.linspace(0,len(depths)-1,min(frames,len(depths))).round().astype(int))
    evidence = []
    for index in indices:
        rotation = Rotation.from_quat(quaternions[index][[1,2,3,0]]).as_matrix()
        check = assess_depth(depths[index],camera_positions[index],rotation,scene,pixels,int(index))
        if check['status']!='passed':raise ValueError('Depth geometry QA failed at frame %d'%index)
        evidence.append({'index':int(index),'checks':check['checks'],'p99_m':check['p99_m'],'max_m':check['max_m']})
    return evidence


def write_shard(folder,flights,scene,qa,config):
    folder = Path(folder);folder.mkdir(parents=True,exist_ok=True)
    depths = np.concatenate([f['depths'] for f in flights],axis=0).astype(np.float32)
    positions = np.concatenate([f['positions'] for f in flights],axis=0)
    quaternions = np.concatenate([f['quaternions'] for f in flights],axis=0)
    camera_positions = np.concatenate([f['camera_positions'] for f in flights],axis=0)
    write_json_atomic(folder/'scene.json',scene)
    np.save(folder/'depth_m.npy',depths)
    np.savez(folder/'poses.npz',positions=positions,quaternions=quaternions,camera_positions=camera_positions)
    manifest = {'status':'complete','config':config,'completed_samples':int(len(depths)),
        'frame_sha256':[hashlib.sha256(np.ascontiguousarray(frame).tobytes()).hexdigest() for frame in depths],
        'qa':qa,'scene_sha256':sha256_file(folder/'scene.json'),'poses_sha256':sha256_file(folder/'poses.npz'),
        'depth_sha256':sha256_file(folder/'depth_m.npy'),
        'provenance':'on-policy closed-loop rollout frames of a locally trained YOPO policy; no expert labels were added',
        'source':'native Isaac PhysX flight through the validated ROS2 planner interface',
        'flights':[{'run':Path(f['folder']).name,'status':f['status'],'scope':f['scope'],
                    'map_seed':f['map_seed'],'frames':int(len(f['depths'])),'checkpoint_sha256':f['checkpoint_sha256'],
                    'flight_sha256':f['flight_sha256'],'metrics_sha256':f['metrics_sha256'],'scene_sha256':f['scene_sha256'],
                    'quaternion_norm_deviation':f['quaternion_norm_deviation']} for f in flights]}
    write_json_atomic(folder/'manifest.json',manifest)
    return manifest


def aggregate(base_root,output_root,flights_root,allow_seeds,qa_count=30,qa_probe=128,sdf_builder=None):
    base_root = Path(base_root).resolve();output_root = Path(output_root).resolve();flights_root = Path(flights_root).resolve()
    if output_root==base_root or base_root in output_root.parents:
        raise ValueError('Aggregation output must not live inside the base dataset')
    base_index = json.loads((base_root/'dataset.json').read_text(encoding='utf-8'))
    if base_index['status']!='complete':raise ValueError('Base dataset is not complete')
    if (output_root/'dataset.json').exists():
        raise ValueError('Aggregation dataset already exists; use a new version name instead of overwriting it')
    if not flights_root.is_dir():raise ValueError('Flights root does not exist: %s'%flights_root)
    base_seeds = {int(shard['map_seed']) for shard in base_index['shards']}
    if base_seeds & set(allow_seeds):raise ValueError('Aggregation maps must not reuse base map seeds')
    if set(allow_seeds) & FORBIDDEN_MAP_SEEDS:raise ValueError('Aggregation maps must not touch validation/test/benchmark seeds')
    base_evidence,base_shard_paths,base_shards = verify_base_shards(base_index,base_root,output_root)
    flights = []
    for folder in resolve_flight_folders(flights_root):
        record = read_flight(folder)
        if record['map_seed'] not in set(allow_seeds):
            raise ValueError('Flight %s used map seed %d outside the declared aggregation set'%(folder.name,record['map_seed']))
        if record['scope'] != 'dagger_aggregation_rollout_not_benchmark':
            raise ValueError('Flight %s does not carry the aggregation scope tag'%folder.name)
        if record['scene']['seed']!=record['map_seed']:raise ValueError('Scene seed differs from the flight map seed')
        flights.append(record)
    if not flights:raise ValueError('No flights found to aggregate')
    by_seed = {}
    for record in flights:by_seed.setdefault(record['map_seed'],[]).append(record)
    builder = sdf_builder
    if builder is None:
        if sys.platform.startswith('win'):builder = docker_sdf_builder
        else:raise ValueError('A concrete SDF builder is required on this platform')
    output_root.mkdir(parents=True,exist_ok=True)
    (output_root/'shards').mkdir(parents=True,exist_ok=True)
    next_id = max(int(shard['id']) for shard in base_index['shards'])+1
    records = []
    for map_seed in sorted(by_seed):
        group = by_seed[map_seed]
        scene = group[0]['scene']
        for record in group[1:]:
            if json.dumps(record['scene'],sort_keys=True)!=json.dumps(scene,sort_keys=True):
                raise ValueError('Flights on map seed %d disagree about scene geometry'%map_seed)
        folder = output_root/'shards'/('%03d'%next_id)
        build_map_assets(folder,scene,builder)
        camera_positions = np.concatenate([f['camera_positions'] for f in group],axis=0)
        quaternions = np.concatenate([f['quaternions'] for f in group],axis=0)
        depths = np.concatenate([f['depths'] for f in group],axis=0)
        qa = qa_frames(depths,camera_positions,quaternions,scene,qa_count,probe=qa_probe)
        config = {'samples':int(len(depths)),'map_seed':int(map_seed),'pose_seed':None,
                  'density':float(scene['density_per_m2']),'geometry_version':2,'raw_shape':list(RAW_SHAPE),
                  'raw_dtype':'float32','depth_unit':'metre',
                  'camera_translation_body_m':list(CAMERA_CONFIG['body_translation_m']),
                  'focal_pixels':CAMERA_CONFIG['fx'],'max_depth_m':MAX_DEPTH_M,'camera_hz':None,
                  'source':'policy rollout through the validated ROS2 interface'}
        write_shard(folder,group,scene,qa,config)
        records.append({'id':int(next_id),'split':'train','map_seed':int(map_seed),'pose_seed':None,
            'samples':int(len(depths)),'density':float(scene['density_per_m2']),
            'path':'shards/'+folder.name,'flights':[Path(f['folder']).name for f in group],
            'manifest_sha256':sha256_file(folder/'manifest.json'),'map_sha256':sha256_file(folder/'map.json')})
        next_id += 1
    index = {'version':1,'status':'complete','scale':'dagger_aggregation',
             'format':base_index['format'],
             'provenance':base_index['provenance']+' plus on-policy DAgger rollout frames; base shard files unmodified',
             'base_dataset_path_rule':'base shard paths are relative to this dataset root; the relative layout of the base dataset must be preserved',
             'shards':base_shards+records}
    write_json_atomic(output_root/'dataset.json',index)
    # Record the base dataset as a path relative to the project root. The stager
    # runs inside the Linux container (ROOT=/workspace); an absolute host path
    # made it fail with FileNotFoundError, while the relative form resolves
    # under /workspace, which is the mounted project root.
    try:
        base_dataset_field = base_root.relative_to(ROOT).as_posix()
    except ValueError:
        base_dataset_field = str(base_root)
    summary = {'status':'complete','scope':'aggregation data version for fine-tuning; not a replacement of base training data',
               'base_dataset':base_dataset_field,'base_dataset_sha256':sha256_file(base_root/'dataset.json'),
               'base_shards_verified':base_evidence,'base_shard_paths':base_shard_paths,'aggregation_shards':records,
               'base_path_rule':'base shard files stay in the base dataset; the aggregation index points at them with relative paths',
               'allow_map_seeds':sorted(int(v) for v in allow_seeds),'qa_frames_per_shard':qa_count,'qa_pixels':qa_probe,
               'camera':CAMERA_CONFIG,
               'limitation':'closed-loop rollouts only exist for the development runner default density; on-policy density coverage is recorded per shard',
               'dataset_sha256':sha256_file(output_root/'dataset.json')}
    write_json_atomic(output_root/'aggregation_manifest.json',summary)
    return summary


def parse_seeds(text):
    seeds = set()
    for part in str(text).split(','):
        part = part.strip()
        if not part:continue
        if '-' in part:
            low,high = part.split('-');seeds.update(range(int(low),int(high)+1))
        else:seeds.add(int(part))
    return seeds


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--flights',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--allow-map-seeds',required=True)
    parser.add_argument('--qa-frames',type=int,default=30)
    parser.add_argument('--qa-pixels',type=int,default=128)
    parser.add_argument('--self-check-frame',type=int,default=-1,
                        help='Index of a frame to re-render independently from the stored scene before aggregation')
    args = parser.parse_args(argv)
    allow = parse_seeds(args.allow_map_seeds)
    if args.self_check_frame>=0:
        folders = resolve_flight_folders(args.flights)
        for folder in folders:
            record = read_flight(folder)
            frame = args.self_check_frame % len(record['depths'])
            pixels = pixel_probe()
            expected = render_reference_frame(record['scene'],record['positions'][frame],record['quaternions'][frame],pixels)
            actual = record['depths'][frame][pixels[:,1],pixels[:,0]]
            error = float(np.max(np.abs(expected-actual)))
            print('SELF_CHECK %s frame %d max_ray_error_m %.6f'%(folder.name,frame,error),flush=True)
    summary = aggregate(args.base,args.output,args.flights,allow,qa_count=args.qa_frames,qa_probe=args.qa_pixels)
    print(json.dumps({k:v for k,v in summary.items() if k!='base_shards_verified'},indent=2,ensure_ascii=False))


if __name__=='__main__':main()
