"""Serial native-Isaac collection and original-C++ SDF build for versioned data."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from yopo_repro.io import write_json_atomic,sha256_file
from yopo_repro.maps import surface_points,write_ply,pointcloud_esdf


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--name',required=True)
    parser.add_argument('--scale',choices=['smoke','full'],required=True)
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    root=(ROOT/'datasets'/args.name).resolve()
    if not root.is_relative_to(ROOT/'datasets'):raise ValueError('Output outside datasets')
    if args.scale=='smoke':
        specs=[('train',100,1000),('train',101,1000),('valid',1000,128),('test',2000,128)]
    else:
        specs=([('train',100+i,5000) for i in range(20)]+[('valid',1000+i,2500) for i in range(4)]+[('test',2000+i,2500) for i in range(4)])
    index={'version':1,'status':'preparing','scale':args.scale,'format':'raw_float_depth_and_body_pose',
           'provenance':'Isaac-equivalent procedural forest, original YOPO bucket SDF',
           'shards':[{'id':i,'split':split,'map_seed':seed,'pose_seed':seed*100+123,'samples':n,
                      'density':1/30 if i%2==0 else 1/20,'path':f'shards/{i:03d}'} for i,(split,seed,n) in enumerate(specs)]}
    if root.exists():
        if not args.resume:raise FileExistsError(root)
        old=json.loads((root/'dataset.json').read_text(encoding='utf-8'))
        if [{k:v for k,v in x.items() if k in index['shards'][0]} for x in old['shards']]!=index['shards']:
            raise ValueError('Existing dataset specification mismatch')
    else:root.mkdir(parents=True)
    write_json_atomic(root/'dataset.json',index)
    for shard in index['shards']:
        destination=root/shard['path']
        command=[sys.executable,str(ROOT/'scripts/collect_isaac_shard.py'),'--output',str(destination),
                 '--samples',str(shard['samples']),'--map-seed',str(shard['map_seed']),
                 '--pose-seed',str(shard['pose_seed']),'--density',str(shard['density'])]
        if args.resume:command.append('--resume')
        env=os.environ.copy();env['OMNI_KIT_ACCEPT_EULA']='YES'
        with (root/f'collect_{shard["id"]:03d}.log').open('a',encoding='utf-8') as log:
            subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        manifest=json.loads((destination/'manifest.json').read_text(encoding='utf-8'))
        if manifest['status']!='complete':raise RuntimeError(f'Shard failed: {destination}')
        metadata_path=destination/'map.json'
        if not metadata_path.exists():
            scene=json.loads((destination/'scene.json').read_text(encoding='utf-8'))
            points=surface_points(scene,.1)
            ply=destination/'pointcloud.ply'
            if not ply.exists():write_ply(ply,points)
            _,occupancy,origin,upper=pointcloud_esdf(points,.2)
            raw=destination/'occupancy.u8';raw.write_bytes(occupancy.astype(np.uint8).tobytes())
            target=destination/'sdf.f32'
            def cp(path):return '/workspace/'+path.relative_to(ROOT).as_posix()
            subprocess.run(['docker','compose','run','--rm','-T','ros','ros2','run','yopo_math_reference','sdf_reference',
                            '--binary',cp(raw),cp(target),*[str(v) for v in occupancy.shape]],cwd=ROOT,check=True)
            values=np.fromfile(target,dtype='<f4').reshape(occupancy.shape)
            if not np.isfinite(values).all():raise RuntimeError('Nonfinite SDF')
            np.save(destination/'sdf.npy',values)
            write_json_atomic(metadata_path,{'backend':'original_main_bucket','origin':origin.tolist(),'upper':upper.tolist(),
                  'resolution':.2,'shape':list(values.shape),'sdf_sha256':sha256_file(destination/'sdf.npy'),'pointcloud_sha256':sha256_file(ply)})
        shard.update(manifest_sha256=sha256_file(destination/'manifest.json'),map_sha256=sha256_file(metadata_path))
        write_json_atomic(root/'dataset.json',index)
        print('DATASET_SHARD_READY '+str(destination),flush=True)
    index['status']='complete';write_json_atomic(root/'dataset.json',index)
    print('DATASET_COMPLETE '+str(root),flush=True)


if __name__=='__main__':main()
