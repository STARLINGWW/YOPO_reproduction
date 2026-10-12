from pathlib import Path
import ctypes,json,sys
import numpy as np
ROOT=Path('/workspace');sys.path.insert(0,str(ROOT/'src'))
from yopo_sim.unified_quad import Quadrotor
lib=ctypes.CDLL(str(ROOT/'ros2_ws/install/yopo_quad_reference/lib/libso3_reference.so'))
pointer=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
lib.so3_reference.argtypes=[pointer,pointer,ctypes.c_double,pointer,ctypes.c_double,ctypes.c_double,pointer]
lib.so3_reference.restype=None
rng=np.random.default_rng(41);quad=Quadrotor();errors=[];limited_errors=[];nonfinite=[]
for i in range(256):
    state=rng.normal(size=(3,3));reference=rng.normal(size=(3,3))*2;yaw=float(rng.uniform(-np.pi,np.pi))
    force,rotation=quad.outer(*state,{'position':reference[0],'velocity':reference[1],'acceleration':reference[2],'yaw':yaw})
    output=np.empty(12);lib.so3_reference(state,reference,yaw,np.r_[quad.kp,quad.kv],quad.mass,quad.gravity,output)
    actual=np.r_[force,rotation.reshape(-1)]
    assert np.isfinite(actual).all(),'Ported controller is non-finite'
    total=(reference-state).sum(axis=0);ka=np.where(np.abs(total)>3,0.,np.abs(total)*.2)
    before=quad.kp*(reference[0]-state[0])+quad.kv*(reference[1]-state[1])+quad.mass*reference[2]+quad.mass*ka*(reference[2]-state[2])+np.array([0.,0.,quad.mass*quad.gravity])
    if not np.isfinite(output).all():
        assert before[2]<0,'Unexpected reference failure outside90-degree limiter'
        nonfinite.append({'case':i,'state':state.tolist(),'reference':reference.tolist(),'yaw':yaw,
                          'force_before_limit':before.tolist(),'ported_output':actual.tolist()})
        continue
    error=float(np.abs(output-actual).max())
    if before[2]<0:
        limited_errors.append(error)
        np.testing.assert_allclose(actual,output,atol=1e-5,rtol=1e-5)
    else:
        errors.append(error)
        np.testing.assert_allclose(actual,output,atol=1e-10,rtol=1e-10)
report={'status':'passed','samples':256,'max_absolute_error':max(errors),
        'normal_cases':len(errors),'limited_finite_cases':len(limited_errors),
        'limited_finite_max_absolute_error':max(limited_errors,default=0.),'original_nonfinite_cases':nonfinite,
        'intentional_numeric_fix':'Clamp roundoff-negative discriminant to0 in upstream90-degree force limiter; original failingcase92 discriminant -7.27596e-12',
        'scope':'Python SO3 outer controller vs original C++ numerical implementation, with explicit limiter numeric exception; dynamics/inner loop require separate PhysX gate'}
(ROOT/'artifacts/environment/quad_controller_parity.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
