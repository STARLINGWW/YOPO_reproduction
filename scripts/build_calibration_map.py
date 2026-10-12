"""Create new map artifacts from a validated scene, without rewriting images."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from yopo_repro.maps import surface_points,write_ply,pointcloud_esdf,VoxelSDF
from yopo_repro.forest import signed_distance


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--dataset",default="calibration_v2")
    parser.add_argument("--output-name")
    args=parser.parse_args()
    dataset=ROOT/"datasets"/args.dataset
    scene=json.loads((dataset/"scene.json").read_text())
    output=ROOT/"artifacts/maps"/(args.output_name or args.dataset)
    output.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter()
    points=surface_points(scene,.1)
    write_ply(output/"pointcloud-0.ply",points)
    values,occ,origin,upper=pointcloud_esdf(points,.2)
    np.save(output/"sdf.npy",values)
    np.save(output/"occupancy.npy",occ)
    field=VoxelSDF(values,origin,.2)
    rng=np.random.default_rng(132)
    samples=[];truth=[]
    while len(samples)<1000:
        p=np.r_[rng.uniform(-30,30,2),rng.uniform(.6,4.)]
        distance=signed_distance(p,scene)
        if distance>.4:
            samples.append(p);truth.append(distance)
    queried,grad,valid=field.query(samples)
    error=np.abs(queried-truth)
    tolerance=np.sqrt(3)*.2+.02
    assert valid.all() and np.isfinite(grad).all()
    assert np.max(error)<tolerance,(np.max(error),tolerance)
    manifest={"status":"passed", "scope":"free-space geometric distance with surface-occupied voxels; compiled upstream SDF comparison pending",
              "scene_sha256":hashlib.sha256((dataset/"scene.json").read_bytes()).hexdigest(),
              "points":len(points),"point_spacing_m":.1,"resolution_m":.2,
              "origin":origin.tolist(),"boundary_upper":upper.tolist(),"shape_xyz":list(values.shape),
              "array_order":"XYZ, C contiguous", "occupancy":"pointcloud surface voxels; interiors are not filled",
              "index_mode":"upstream_truncate, multiply inverse resolution before integer conversion",
              "gradient":"cellwise central differences, one-sided at edges",
              "free_space_checks":1000,"max_distance_error_m":float(error.max()),"p95_distance_error_m":float(np.percentile(error,95)),
              "distance_tolerance_m":float(tolerance),"elapsed_s":time.perf_counter()-started,
              "files":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}}
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps(manifest,indent=2))


if __name__=="__main__":main()
