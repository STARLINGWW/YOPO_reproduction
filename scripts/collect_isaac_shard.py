"""Resumable raw-float Isaac forest depth shard, with fixed paired poses.

Contains no policy or pretrained weights. Uses the validated explicit geometry
and optical-depth convention. The parent runner must check manifest.status;
Isaac's fast shutdown can mask the process exception exit code.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time
import traceback
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from yopo_repro.forest import generate,signed_distance,ray_depth,author_scene
from yopo_repro.io import sha256_file,write_json_atomic
from depth_quality import assess_depth


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--samples',type=int,required=True)
    parser.add_argument('--map-seed',type=int,required=True)
    parser.add_argument('--pose-seed',type=int,required=True)
    parser.add_argument('--density',type=float,default=1/30)
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to(ROOT) or not 1<=args.samples<=10000:
        parser.error('Output must be inside the project; samples must be 1..10000')
    config={'samples':args.samples,'map_seed':args.map_seed,'pose_seed':args.pose_seed,'density':args.density,
            'geometry_version':2,'raw_shape':[90,160],'raw_dtype':'float32','depth_unit':'metre',
            'camera_translation_body_m':[0.,0.,.1],'focal_pixels':80.,'max_depth_m':20.,
            'roll_pitch_std_rad':.1,'capture_updates_after_pose':2}
    manifest_path=output/'manifest.json'
    if output.exists():
        if not args.resume:raise FileExistsError(output)
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest['config']!=config:raise ValueError('Resume config mismatch')
        if manifest['status']=='complete':
            assert sha256_file(output/'depth_m.npy')==manifest['depth_sha256']
            print('SHARD_ALREADY_COMPLETE '+str(output),flush=True);return
        scene=json.loads((output/'scene.json').read_text(encoding='utf-8'))
        labels=dict(np.load(output/'poses.npz'))
        data=np.lib.format.open_memmap(output/'depth_m.npy',mode='r+')
        first=manifest['completed_samples']
    else:
        output.mkdir(parents=True)
        scene=generate(args.map_seed,args.density)
        (output/'scene.json').write_text(json.dumps(scene,indent=2),encoding='utf-8')
        from scipy.spatial.transform import Rotation
        rng=np.random.default_rng(args.pose_seed)
        positions=[];quaternions=[];camera_positions=[]
        for i in range(args.samples):
            for _ in range(10000):
                p=np.r_[rng.uniform(-30,30,2),rng.uniform(1.5,3.5)]
                if signed_distance(p,scene)>=.6:break
            else:raise RuntimeError('No valid free-space sample')
            yaw=rng.uniform(-np.pi,np.pi);pitch,roll=rng.normal(0.,.1,2)
            rotation=Rotation.from_euler('ZYX',[yaw,pitch,roll])
            q=rotation.as_quat()[[3,0,1,2]]
            camera_position=p+rotation.as_matrix()@np.array([0.,0.,.1])
            positions.append(p);quaternions.append(q);camera_positions.append(camera_position)
        labels={'positions':np.asarray(positions),'quaternions':np.asarray(quaternions),'camera_positions':np.asarray(camera_positions)}
        np.savez_compressed(output/'poses.npz',**labels)
        data=np.lib.format.open_memmap(output/'depth_m.npy',mode='w+',dtype=np.float32,shape=(args.samples,90,160))
        manifest={'status':'initialized','config':config,'completed_samples':0,'frame_sha256':[], 'qa':[],
                  'scene_sha256':sha256_file(output/'scene.json'),'poses_sha256':sha256_file(output/'poses.npz'),
                  'provenance':scene['provenance'],'source':'Isaac Sim 6.1 distance_to_image_plane'}
        write_json_atomic(manifest_path,manifest);first=0
    assert data.shape==(args.samples,90,160) and data.dtype==np.float32
    assert sha256_file(output/'poses.npz')==manifest['poses_sha256']
    assert sha256_file(output/'scene.json')==manifest['scene_sha256']
    # Discard only metadata for uncommitted partial frames after interruption.
    manifest['frame_sha256']=manifest['frame_sha256'][:first]
    manifest['qa']=[row for row in manifest['qa'] if row['index']<first]
    from isaacsim import SimulationApp
    app=SimulationApp({'headless':True,'enable_cameras':True,'width':320,'height':180})
    try:
        import omni.usd
        import omni.replicator.core as rep
        from isaacsim.core.api import World
        from pxr import Gf,UsdGeom
        from scipy.spatial.transform import Rotation
        import cv2
        omni.usd.get_context().new_stage();stage=omni.usd.get_context().get_stage()
        author_scene(stage,scene)
        camera=UsdGeom.Camera.Define(stage,'/World/Camera')
        camera.CreateFocalLengthAttr(18.);camera.CreateHorizontalApertureAttr(36.)
        camera.CreateVerticalApertureAttr(20.25);camera.CreateClippingRangeAttr((.04,40.))
        xf=UsdGeom.Xformable(camera);translate=xf.AddTranslateOp();orient=xf.AddOrientOp()
        product=rep.create.render_product('/World/Camera',(160,90))
        annotator=rep.AnnotatorRegistry.get_annotator('distance_to_image_plane');annotator.attach(product)
        world=World(stage_units_in_meters=1.);world.reset()
        rng=np.random.default_rng(817)
        pixels=np.column_stack([rng.integers(4,156,128),rng.integers(4,86,128)])
        rays=np.column_stack([np.ones(128),-(pixels[:,0]+.5-80)/80,-(pixels[:,1]+.5-45)/80])
        started=time.perf_counter()
        for i in range(first,args.samples):
            q=labels['quaternions'][i];matrix=Rotation.from_quat(q[[1,2,3,0]]).as_matrix()
            p=labels['camera_positions'][i]
            usd_rotation=np.column_stack([-matrix[:,1],matrix[:,2],-matrix[:,0]])
            usd_q=Rotation.from_matrix(usd_rotation).as_quat()
            translate.Set(Gf.Vec3d(*p.tolist()));orient.Set(Gf.Quatf(float(usd_q[3]),Gf.Vec3f(*usd_q[:3].tolist())))
            for _ in range(12 if i==first else 2):rep.orchestrator.step(delta_time=0.,rt_subframes=1)
            depth=np.asarray(annotator.get_data(),dtype=np.float32).reshape(90,160).copy()
            depth=np.clip(np.nan_to_num(depth,nan=20.,posinf=20.,neginf=0.),0.,20.)
            assert np.isfinite(depth).all()
            if i<10 or i%100==0 or i==args.samples-1:
                qa=assess_depth(depth,p,matrix,scene,pixels,i)
                if qa['status']!='passed':
                    np.save(output/f'failed_depth_{i}.npy',depth)
                    raise RuntimeError(f'Ray geometry mismatch: {qa}')
                manifest['qa'].append(qa)
            data[i]=depth
            manifest['frame_sha256'].append(hashlib.sha256(depth.tobytes()).hexdigest())
            if (i+1)%50==0 or i+1==args.samples:
                data.flush();manifest['completed_samples']=i+1;manifest['status']='collecting'
                write_json_atomic(manifest_path,manifest)
                print(f'SHARD {output.name}: {i+1}/{args.samples} elapsed={time.perf_counter()-started:.1f}s',flush=True)
        data.flush()
        manifest.update(status='complete',depth_sha256=sha256_file(output/'depth_m.npy'),capture_elapsed_s=time.perf_counter()-started,
                        qa_policy='ray_match_with_explicit_0.001_pixel_silhouette_bound_v1')
        cv2.imwrite(str(output/'preview_depth16.png'),np.rint(data[0]/20.*65535).astype(np.uint16))
        write_json_atomic(manifest_path,manifest)
        print('SHARD_COMPLETE '+str(output),flush=True)
    except Exception:
        manifest.update(status='interrupted',traceback=traceback.format_exc())
        write_json_atomic(manifest_path,manifest);print(manifest['traceback'],flush=True)
    finally:app.close()


if __name__=='__main__':main()
