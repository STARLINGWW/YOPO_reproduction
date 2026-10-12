"""Use original bucket-distance code for the primary map cache, not SciPy EDT."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser()
parser.add_argument('--map',default='calibration_v2_upstream_index')
parser.add_argument('--output',default='calibration_v2_main_backend')
args=parser.parse_args()
source=ROOT/'artifacts/maps'/args.map
output=ROOT/'artifacts/maps'/args.output
output.mkdir(parents=True,exist_ok=False)
metadata=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
occupancy=np.load(source/'occupancy.npy')
raw=output/'occupancy.u8';raw.write_bytes(occupancy.astype(np.uint8).tobytes())
def container_path(path):return '/workspace/'+path.relative_to(ROOT).as_posix()
started=time.perf_counter()
subprocess.run(['docker','compose','run','--rm','-T','ros','ros2','run','yopo_math_reference','sdf_reference',
                '--binary',container_path(raw),container_path(output/'sdf.f32'),*[str(n) for n in occupancy.shape]],check=True,cwd=ROOT)
values=np.fromfile(output/'sdf.f32',dtype='<f4').reshape(occupancy.shape)
np.save(output/'sdf.npy',values)
scipy=np.load(source/'sdf.npy')
error=np.abs(scipy-values)
report={'status':'built','backend':'original_main_bucket_distance_transform',
        'source_map':str(source.relative_to(ROOT)),'origin':metadata['origin'],'boundary_upper':metadata['boundary_upper'],
        'shape_xyz':list(occupancy.shape),'resolution_m':metadata['resolution_m'],
        'scipy_differences':{'count_over_1e_6':int((error>1e-6).sum()),'max_m':float(error.max())},
        'elapsed_s':time.perf_counter()-started,
        'sdf_sha256':hashlib.sha256((output/'sdf.npy').read_bytes()).hexdigest(),
        'note':'SciPy EDT is retained only as an independent diagnostic. Primary training uses the original numerical backend.'}
(output/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2),flush=True)
