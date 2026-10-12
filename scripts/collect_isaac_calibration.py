"""Collect paired Isaac depth/pose calibration samples and independently ray-check them.

No network, checkpoint or policy is used. This is the 100-sample geometry gate,
not the approved 100K training dataset. Existing dataset versions are refused.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
import time
import traceback
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from yopo_repro.forest import generate, signed_distance, ray_depth, author_scene


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="calibration_v1")
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--map-seed", type=int, default=100)
    parser.add_argument("--pose-seed", type=int, default=10000)
    args = parser.parse_args()
    if args.samples < 1 or args.samples > 1000:
        parser.error("calibration collector limited to 1..1000 samples")
    output = ROOT / "datasets" / args.name
    output.mkdir(parents=True, exist_ok=False)
    (output / "0").mkdir()
    scene = generate(args.map_seed)
    (output / "scene.json").write_text(json.dumps(scene, indent=2), encoding="utf-8")
    camera_config = {"resolution_wh":[160,90], "fx":80., "fy":80., "cx":80., "cy":45.,
                     "max_depth_m":20., "t_BC_m":[0.,0.,.1], "planning_frame":"FLU", "quaternion":"wxyz"}
    manifest = {"status":"running", "scope":"calibration_only_not_training", "config":vars(args),
                "camera":camera_config, "source":"Isaac Sim 6.1 distance_to_image_plane",
                "provenance":scene["provenance"], "samples":[]}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    from isaacsim import SimulationApp
    app = SimulationApp({"headless":True, "enable_cameras":True, "width":320,"height":180})
    try:
        import omni.usd
        import omni.replicator.core as rep
        from isaacsim.core.api import World
        from pxr import Gf, UsdGeom
        from scipy.spatial.transform import Rotation
        import cv2
        omni.usd.get_context().new_stage()
        stage = omni.usd.get_context().get_stage()
        author_scene(stage, scene)
        camera = UsdGeom.Camera.Define(stage, "/World/Camera")
        camera.CreateFocalLengthAttr(18.)
        camera.CreateHorizontalApertureAttr(36.)
        camera.CreateVerticalApertureAttr(20.25)
        camera.CreateClippingRangeAttr((.04,40.))
        xf = UsdGeom.Xformable(camera)
        translate, orient = xf.AddTranslateOp(), xf.AddOrientOp()
        product = rep.create.render_product("/World/Camera", (160,90))
        annotator = rep.AnnotatorRegistry.get_annotator("distance_to_image_plane")
        annotator.attach(product)
        world = World(stage_units_in_meters=1.)
        world.reset()
        rng = np.random.default_rng(args.pose_seed)
        pixels = np.column_stack([rng.integers(4,156,128), rng.integers(4,86,128)])
        rays_body = np.column_stack([np.ones(len(pixels)), -(pixels[:,0]+.5-80)/80, -(pixels[:,1]+.5-45)/80])
        positions, quaternions, camera_positions, ray_errors = [], [], [], []
        elapsed = []
        for i in range(args.samples):
            for attempt in range(10000):
                p = np.r_[rng.uniform(-30,30,2), rng.uniform(1.5,3.5)]
                if signed_distance(p, scene) >= .6:
                    break
            else:
                raise RuntimeError("unable to sample free position")
            yaw = rng.uniform(-np.pi,np.pi)
            pitch, roll = rng.normal(0.,.1,2)
            rotation = Rotation.from_euler("ZYX", [yaw,pitch,roll])
            matrix = rotation.as_matrix()
            camera_p = p + matrix @ np.array(camera_config["t_BC_m"])
            usd_rotation = np.column_stack([-matrix[:,1], matrix[:,2], -matrix[:,0]])
            usd_q = Rotation.from_matrix(usd_rotation).as_quat()
            translate.Set(Gf.Vec3d(*camera_p.tolist()))
            orient.Set(Gf.Quatf(float(usd_q[3]), Gf.Vec3f(*usd_q[:3].tolist())))
            started = time.perf_counter()
            # Repeat capture after a pose change to flush stale render products.
            for _ in range(12 if i == 0 else 2):
                rep.orchestrator.step(delta_time=0., rt_subframes=1)
            depth = np.asarray(annotator.get_data(), dtype=np.float32).reshape(90,160).copy()
            depth = np.clip(np.nan_to_num(depth, nan=20., posinf=20., neginf=0.),0.,20.)
            expected = ray_depth(camera_p, rays_body @ matrix.T, scene)
            actual = depth[pixels[:,1], pixels[:,0]]
            errors = np.abs(actual-expected)
            ray_errors.extend(errors.tolist())
            image_path = output / "0" / f"img_{i}.png"
            assert cv2.imwrite(str(image_path), np.rint(depth / 20. * 65535).astype(np.uint16))
            q = rotation.as_quat()[[3,0,1,2]]
            positions.append(p); quaternions.append(q); camera_positions.append(camera_p)
            manifest["samples"].append({"index":i, "image":f"0/img_{i}.png", "position_w":p.tolist(),
                                        "quaternion_wxyz":q.tolist(), "camera_position_w":camera_p.tolist(),
                                        "sha256":hashlib.sha256(image_path.read_bytes()).hexdigest(),
                                        "ray_check_p95_m":float(np.percentile(errors,95))})
            elapsed.append(time.perf_counter()-started)
            if i % 20 == 0:
                print(f"CALIBRATION {i+1}/{args.samples} ray P95={np.percentile(errors,95):.4f}m",flush=True)
        np.savez_compressed(output/"0/label.npz",positions=positions,quaternions=quaternions,camera_positions=camera_positions)
        np.savetxt(output/"pose-0.csv",np.column_stack([positions,quaternions]),delimiter=",",header="px,py,pz,qw,qx,qy,qz",comments="")
        outlier_fraction = float(np.mean(np.asarray(ray_errors) > .2))
        metrics = {"status":"passed" if np.percentile(ray_errors,99)<.1 and outlier_fraction<.001 else "needs_outlier_audit",
                   "samples":args.samples,"ray_checks":len(ray_errors),"median_error_m":float(np.median(ray_errors)),
                   "p95_error_m":float(np.percentile(ray_errors,95)),"max_error_m":float(np.max(ray_errors)),
                   "p99_error_m":float(np.percentile(ray_errors,99)), "fraction_over_20cm":outlier_fraction,
                   "capture_and_write_median_s_excluding_first":float(np.median(elapsed[1:] if len(elapsed)>1 else elapsed)),
                   "trees":len(scene["trees"]),"shrubs":len(scene["shrubs"]),
                   "scope":"paired pose/depth and independent ray geometry; pointcloud/ESDF gate not yet covered"}
        manifest["status"] = metrics["status"]
        (output/"validation.json").write_text(json.dumps(metrics,indent=2),encoding="utf-8")
        print("CALIBRATION_RESULT "+json.dumps(metrics),flush=True)
    except Exception:
        manifest["status"]="failed"
        manifest["traceback"]=traceback.format_exc()
        print(manifest["traceback"],flush=True)
    finally:
        (output/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
        app.close()


if __name__=="__main__":
    main()
