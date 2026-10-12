"""Read back every shard and verify file/pose/frame integrity and split isolation."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import numpy as np
from scipy.spatial.transform import Rotation

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from yopo_repro.io import sha256_file,write_json_atomic
from depth_quality import assess_depth

parser=argparse.ArgumentParser()
parser.add_argument('--dataset',type=Path,required=True)
args=parser.parse_args();root=args.dataset.resolve()
index=json.loads((root/'dataset.json').read_text(encoding='utf-8'))
assert index['status']=='complete'
seeds=set();counts={};checks=[]
for shard in index['shards']:
    folder=root/shard['path'];assert shard['map_seed'] not in seeds;seeds.add(shard['map_seed'])
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    maps=json.loads((folder/'map.json').read_text(encoding='utf-8'))
    assert sha256_file(folder/'manifest.json')==shard['manifest_sha256']
    assert sha256_file(folder/'map.json')==shard['map_sha256']
    for name,key in [('depth_m.npy','depth_sha256'),('poses.npz','poses_sha256'),('scene.json','scene_sha256')]:
        assert sha256_file(folder/name)==manifest[key]
    assert maps['backend']=='original_main_bucket'
    assert sha256_file(folder/'sdf.npy')==maps['sdf_sha256']
    assert sha256_file(folder/'pointcloud.ply')==maps['pointcloud_sha256']
    depth=np.load(folder/'depth_m.npy',mmap_mode='r');poses=np.load(folder/'poses.npz')
    assert depth.shape==(shard['samples'],90,160) and depth.dtype==np.float32
    assert poses['positions'].shape==(len(depth),3) and poses['quaternions'].shape==(len(depth),4)
    assert np.isfinite(poses['positions']).all()
    assert np.max(abs(np.linalg.norm(poses['quaternions'],axis=1)-1))<1e-10
    assert len(manifest['frame_sha256'])==len(depth)
    for i,frame in enumerate(depth):
        assert np.isfinite(frame).all() and frame.min()>=0 and frame.max()<=20
        assert hashlib.sha256(frame.tobytes()).hexdigest()==manifest['frame_sha256'][i]
    qa=manifest['qa'];assert qa
    scene=json.loads((folder/'scene.json').read_text(encoding='utf-8'))
    rng=np.random.default_rng(817);pixels=np.column_stack([rng.integers(4,156,128),rng.integers(4,86,128)])
    verified=[]
    for saved in qa:
        i=saved['index'];q=poses['quaternions'][i]
        matrix=Rotation.from_quat(q[[1,2,3,0]]).as_matrix()
        check=assess_depth(depth[i],poses['camera_positions'][i],matrix,scene,pixels,i)
        assert check['status']=='passed',check
        verified.append(check)
    counts[shard['split']]=counts.get(shard['split'],0)+len(depth)
    checks.append({'id':shard['id'],'map_seed':shard['map_seed'],'split':shard['split'],'samples':len(depth),
                   'ray_checked_frames':len(qa),'max_raw_ray_error_m':max(x['max_m'] for x in verified),
                   'subpixel_ambiguous_pixels':sum(len(x['ambiguous_pixels']) for x in verified),
                   'unresolved_pixels':sum(len(x['unresolved_pixels']) for x in verified)})
report={'status':'passed','counts':counts,'shards':checks,'dataset_sha256':sha256_file(root/'dataset.json'),
        'scope':'all stored depth frames, hashes, poses, map provenance and disjoint map seeds; not navigation performance'}
write_json_atomic(root/'validation.json',report)
print(json.dumps(report,indent=2))
