"""Reproduce a failed depth/pose check without modifying the dataset shard."""
from pathlib import Path
import argparse
import json
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from yopo_repro.forest import author_scene,ray_depth

parser=argparse.ArgumentParser()
parser.add_argument('--shard',type=Path,required=True)
parser.add_argument('--index',type=int,required=True)
parser.add_argument('--name',required=True)
args=parser.parse_args()
output=ROOT/'artifacts/diagnostics'/args.name;output.mkdir(parents=True,exist_ok=False)
scene=json.loads((args.shard/'scene.json').read_text(encoding='utf-8'));labels=np.load(args.shard/'poses.npz')
from isaacsim import SimulationApp
app=SimulationApp({'headless':True,'enable_cameras':True,'width':320,'height':180})
try:
    import omni.usd
    import omni.replicator.core as rep
    from isaacsim.core.api import World
    from pxr import Gf,UsdGeom
    from scipy.spatial.transform import Rotation
    import cv2
    omni.usd.get_context().new_stage();stage=omni.usd.get_context().get_stage();author_scene(stage,scene)
    camera=UsdGeom.Camera.Define(stage,'/World/Camera')
    camera.CreateFocalLengthAttr(18.);camera.CreateHorizontalApertureAttr(36.);camera.CreateVerticalApertureAttr(20.25)
    camera.CreateClippingRangeAttr((.04,40.))
    q=labels['quaternions'][args.index];matrix=Rotation.from_quat(q[[1,2,3,0]]).as_matrix();p=labels['camera_positions'][args.index]
    usd_rotation=np.column_stack([-matrix[:,1],matrix[:,2],-matrix[:,0]])
    usd_q=Rotation.from_matrix(usd_rotation).as_quat()
    xf=UsdGeom.Xformable(camera);xf.AddTranslateOp().Set(Gf.Vec3d(*p.tolist()));xf.AddOrientOp().Set(Gf.Quatf(float(usd_q[3]),Gf.Vec3f(*usd_q[:3].tolist())))
    product=rep.create.render_product('/World/Camera',(160,90))
    annotator=rep.AnnotatorRegistry.get_annotator('distance_to_image_plane');annotator.attach(product)
    world=World(stage_units_in_meters=1.);world.reset()
    for _ in range(16):rep.orchestrator.step(delta_time=0.,rt_subframes=1)
    depth=np.asarray(annotator.get_data(),dtype=np.float32).reshape(90,160).copy()
    depth=np.clip(np.nan_to_num(depth,nan=20.,posinf=20.,neginf=0.),0.,20.)
    np.save(output/'depth.npy',depth)
    cv2.imwrite(str(output/'depth.png'),cv2.applyColorMap(np.uint8(depth/20*255),cv2.COLORMAP_TURBO))
    rng=np.random.default_rng(817);pixels=np.column_stack([rng.integers(4,156,128),rng.integers(4,86,128)])
    def ray(pix):return np.column_stack([np.ones(len(pix)),-(pix[:,0]+.5-80)/80,-(pix[:,1]+.5-45)/80])@matrix.T
    expected=ray_depth(p,ray(pixels),scene);actual=depth[pixels[:,1],pixels[:,0]];errors=abs(expected-actual)
    outliers=[]
    for j in np.flatnonzero(errors>.1):
        pixel=pixels[j];offsets=np.array([(x,y) for x in [-.001,0,.001] for y in [-.001,0,.001]])
        depths=ray_depth(p,ray(pixel[None]+offsets),scene)
        u,v=pixel
        outliers.append({'pixel':pixel.tolist(),'expected':float(expected[j]),'actual':float(actual[j]),
                          'subpixel_depths':depths.tolist(),'subpixel_closest_error':float(min(abs(depths-actual[j]))),
                          'neighbor_depths':depth[v-1:v+2,u-1:u+2].tolist()})
    report={'index':args.index,'max_error_m':float(errors.max()),'p99_m':float(np.percentile(errors,99)),'outliers':outliers}
    (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2),flush=True)
finally:app.close()
