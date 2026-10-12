"""CPU diagnostic of the common motor/controller design, NOT PhysX proof."""
from pathlib import Path
import json
import sys
import numpy as np
from scipy.spatial.transform import Rotation
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from yopo_sim.unified_quad import Quadrotor,circle_reference

results=[]
for speed in [0.,2.,4.,6.,8.,10.]:
    model=Quadrotor();dt=model.config['physics_dt_s'];p=np.array([0.,0.,3.]);v=np.zeros(3);a=np.zeros(3)
    rotation=np.eye(3);omega=np.zeros(3);errors=[];speeds=[];saturated=[]
    force,desired=model.outer(p,v,a,circle_reference(0,speed))
    for k in range(round(10/dt)):
        t=k*dt;reference=circle_reference(t,speed)
        if k%5==0:force,desired=model.outer(p,v,a,reference)
        fw,tw,debug=model.step_wrench(rotation,omega,v,force,desired,dt)
        a=fw/model.mass-np.array([0.,0.,model.gravity])
        angular_acc=(rotation.T@tw-np.cross(omega,model.inertia*omega))/model.inertia
        rotation=rotation@Rotation.from_rotvec((omega+.5*dt*angular_acc)*dt).as_matrix()
        omega+=dt*angular_acc;p+=v*dt+.5*a*dt*dt;v+=a*dt
        errors.append(np.linalg.norm(p-reference['position']));saturated.append(debug['saturated'])
        if t>=5:speeds.append(np.linalg.norm(v))
    results.append({'target_mps':speed,'tracking_rmse_m':float(np.sqrt(np.mean(np.square(errors)))),
        'max_error_m':float(max(errors)),'steady_mean_speed_mps':float(np.mean(speeds)),
        'saturation_fraction':float(np.mean(saturated))})
    print(results[-1],flush=True)
report={'scope':'CPU rigid-body approximation for model/controller preflight; not Isaac or flight benchmark',
        'status':'passed' if all(v['tracking_rmse_m']<.5 and v['max_error_m']<1. for v in results) else 'needs_tuning',
        'cases':results}
(ROOT/'artifacts/environment/unified_quad_cpu.json').write_text(json.dumps(report,indent=2)+'\n')
print(report['status'])
