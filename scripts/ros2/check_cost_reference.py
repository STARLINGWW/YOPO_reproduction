"""Raw cost/gradient parity with unchanged upstream C++ and injected plane SDF."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from yopo_repro.main_cost import cost_and_gradient

class Plane:
    resolution=.2
    def query(self,p):
        return p[:,2].astype(np.float32).astype(float),np.tile([0.,0.,1.],(len(p),1)),np.ones(len(p),dtype=bool)

rng=np.random.default_rng(23)
start=rng.normal(0,.5,(32,3,3));start[:,2,0]+=2
end=start.copy();end[:,0,0]+=rng.uniform(2.,8.,32);end[:,2,0]+=rng.uniform(-.5,2,32)
goals=start[:,:,0]+[8.,0.,0.]
rows=np.concatenate([start.reshape(-1,9),end.reshape(-1,9),goals],axis=1)
payload='\n'.join(' '.join(format(v,'.17g') for v in row) for row in rows)+'\n'
config=ROOT/'external/audit_sources/main/flightlib/configs/traj_opt.yaml'
reference=json.loads(subprocess.check_output(['ros2','run','yopo_math_reference','cost_reference',str(config)],input=payload,text=True))
cost,gradient,_=cost_and_gradient(start,end,goals,Plane(),[-100]*3,[100]*3)
expected=np.array([row['cost'] for row in reference])
expected_grad=np.array([row['gradient'] for row in reference]).reshape(-1,3,3)
np.testing.assert_allclose(cost,expected,rtol=1e-6,atol=5e-8)
np.testing.assert_allclose(gradient,expected_grad,rtol=1e-6,atol=5e-8)
source=ROOT/'external/audit_sources/main/flightlib/src/grad_traj_optimization/grad_traj_optimizer.cpp'
report={'status':'passed','cases':len(rows),'scope':'original trajectory cost/Jacobian with analytic-plane SDF test double; real ESDF construction still separate',
        'max_cost_error':float(np.max(abs(cost-expected))),'max_gradient_error':float(np.max(abs(gradient-expected_grad))),
        'upstream_optimizer_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
(ROOT/'artifacts/environment/cost_cpp_parity.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
