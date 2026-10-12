"""Compare SciPy EDT against extracted unmodified upstream bucket algorithm."""
from pathlib import Path
import argparse
import json
import subprocess
import numpy as np
from scipy.ndimage import distance_transform_edt

ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser()
parser.add_argument('--docker',action='store_true')
args=parser.parse_args()
command=['ros2','run','yopo_math_reference','sdf_reference']
if args.docker:command=['docker','compose','run','--rm','-T','ros']+command
cases=[]
plane=np.zeros((12,13,14),dtype=bool);plane[:,:,0]=True;cases.append(('plane',plane))
single=np.zeros((12,13,14),dtype=bool);single[3,4,5]=True;cases.append(('single',single))
for seed,density in [(0,.01),(1,.03),(2,.2),(3,.5)]:
    cases.append((f'random_{seed}',np.random.default_rng(seed).random((19,17,13))<density))
results=[]
for name,occupied in cases:
    payload=' '.join(str(v) for v in occupied.shape)+'\n'+' '.join(str(int(x)) for x in occupied.ravel())+'\n'
    values=np.array(json.loads(subprocess.check_output(command,input=payload,text=True,cwd=ROOT)),dtype=np.float32).reshape(occupied.shape)
    expected=((distance_transform_edt(~occupied)-distance_transform_edt(occupied))*.2).astype(np.float32)
    error=np.abs(values-expected)
    results.append({'case':name,'voxels':occupied.size,'max_error':float(error.max()),'mismatched_gt_1e_6':int((error>1e-6).sum())})
report={'status':'passed' if all(x['max_error']<1e-6 for x in results) else 'difference_found',
        'scope':'six complete small occupancy grids compared with original distance-transform function bodies', 'cases':results}
(ROOT/'artifacts/environment/sdf_cpp_parity.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
raise SystemExit(0 if report['status']=='passed' else 1)
