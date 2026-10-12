"""Full-field original-C++ parity plus declared50-budget expert diagnostics."""
from pathlib import Path
import json,sys,time
import numpy as np
import yaml
ROOT=Path('/workspace');sys.path.insert(0,str(ROOT/'src'))
from yopo_expert.core import ExpertMap,world_problem
from yopo_repro.policy import load_config,MapBank
from yopo_repro.dataset import ForestDataset,stack_batch
from yopo_repro.main_cost import cost_and_gradient
from yopo_repro.quintic import matrices
from flightpolicy.yopo.primitive_utils import LatticeParam,LatticePrimitive

profile,cfg=load_config();dataset=ForestDataset(ROOT/'datasets/smoke_v1','train',cfg,seed=0)
depth,positions,rotations,observations,ids=stack_batch(dataset,np.arange(16))
lattice=LatticePrimitive(LatticeParam(cfg));initial=np.zeros((16,15,3,3))
initial[:,:,:,0]=lattice.lattice_pos_node[::-1];initial[:,:,:,1]=lattice.lattice_vel_node[::-1]
starts,ends,goals=world_problem(positions,rotations,observations,initial)
bank=MapBank(ROOT/'datasets/smoke_v1',dataset.shards,cfg);sdf,lower,upper=bank.maps[0]
expert=ExpertMap(ROOT/'datasets/smoke_v1/shards/000')
cpp_cost,cpp_gradient=expert.evaluate(starts,ends,goals)
py_cost,py_gradient,_=cost_and_gradient(starts,ends,goals,sdf,lower,upper,bank.config)
cost_error=float(np.abs(cpp_cost-py_cost).max());gradient_error=float(np.abs(cpp_gradient-py_gradient).max())
np.testing.assert_allclose(cpp_cost,py_cost,rtol=1e-7,atol=1e-8)
np.testing.assert_allclose(cpp_gradient,py_gradient,rtol=1e-5,atol=2e-7)
edge_start=np.zeros((4,3,3));edge_start[:,:,0]=[[38,0,3],[-38,0,3],[0,38,3],[0,0,7.]]
edge_end=edge_start.copy();edge_end[:,:,0]=[[42,0,3],[-42,0,3],[0,42,3],[0,0,9.]]
edge_goal=edge_end[:,:,0].copy()
ec,eg=expert.evaluate(edge_start,edge_end,edge_goal)
pc,pg,_=cost_and_gradient(edge_start,edge_end,edge_goal,sdf,lower,upper,bank.config)
np.testing.assert_allclose(ec,pc,rtol=1e-7,atol=1e-8);np.testing.assert_allclose(eg,pg,rtol=1e-5,atol=2e-7)
variants={}
for name in ['scaled_gd50','mma50_evaluations']:
    before=time.perf_counter();optimized,values,diagnostics=expert.optimize(starts,ends,goals,name);wall=time.perf_counter()-before
    checked,_=expert.evaluate(starts,optimized,goals)
    np.testing.assert_allclose(checked,values,atol=1e-10,rtol=1e-10)
    assert np.isfinite(optimized).all() and np.all(values<=cpp_cost+1e-12)
    variants[name]={'initial_mean_cost':float(cpp_cost.mean()),'final_mean_cost':float(values.mean()),
        'initial_mean_best_of15':float(cpp_cost.reshape(-1,15).min(1).mean()),'final_mean_best_of15':float(values.reshape(-1,15).min(1).mean()),
        'objective_evaluations_minmax':[int(diagnostics[:,0].min()),int(diagnostics[:,0].max())],
        'accepted_gd_updates_minmax':[int(diagnostics[:,1].min()),int(diagnostics[:,1].max())],
        'nonfinite_evaluations':int(diagnostics[:,3].sum()),'core_ms_per15_mean':float(diagnostics[:,4].reshape(-1,15).sum(1).mean()),'outer_wall_s':wall}
expert.close()
out=ROOT/'artifacts/expert';out.mkdir(exist_ok=True)
report={'status':'passed','scope':'Development map numerical and solver diagnostics; not TableI test-set results or exact unpublished expert replication',
        'samples':16,'trajectories':240,'cost_max_error':cost_error,'gradient_max_error':gradient_error,
        'out_of_grid_boundary_cases':4,'boundary_gradient_max_error':float(np.abs(eg-pg).max()),'variants':variants}
(out/'core_probe.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
