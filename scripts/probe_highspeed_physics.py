"""Actual native Isaac PhysX validation of shared force/motor control up to10m/s.

No neural planner, map, teleport after reset, or ideal acceleration actuation.
This is a plant/controller gate, not closed-loop navigation evidence.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time
import traceback
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from yopo_sim.unified_quad import Quadrotor,circle_reference
from yopo_sim.job_guard import require_training_gpu_released


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',default='physx_unified_v1');args=parser.parse_args()
    if not args.run.replace('_','').replace('-','').isalnum():raise ValueError('Invalid run name')
    require_training_gpu_released()
    output=ROOT/'artifacts/control_validation'/args.run;output.mkdir(parents=True,exist_ok=False)
    report={'status':'running','scope':'Actual PhysX force-driven vehicle/controller in empty space; not a learned navigation benchmark',
            'config':json.loads((ROOT/'configs/unified_quad.json').read_text()),
            'config_sha256':hashlib.sha256((ROOT/'configs/unified_quad.json').read_bytes()).hexdigest(),
            'cases':[]}
    (output/'result.json').write_text(json.dumps(report,indent=2))
    app=None
    try:
        from isaacsim import SimulationApp
        app=SimulationApp({'headless':True,'enable_cameras':False})
        import omni.usd
        from isaacsim.core.api import World
        from isaacsim.core.prims import RigidPrim
        from yopo_sim.physx_vehicle import author_vehicle,author_floor,read_state
        omni.usd.get_context().new_stage();stage=omni.usd.get_context().get_stage()
        author_floor(stage);author_vehicle(stage,report['config'])
        dt=report['config']['physics_dt_s']
        world=World(stage_units_in_meters=1.,physics_dt=dt,rendering_dt=.02)
        body=world.scene.add(RigidPrim('/World/Quadrotor',name='common_quadrotor',track_contact_forces=True))
        stage.Export(str(output/'vehicle_scene.usda'))
        for speed in [0.,2.,4.,6.,8.,10.]:
            world.reset()
            observed_mass=float(np.asarray(body.get_masses())[0])
            observed_inertia=np.asarray(body.get_inertias())[0].reshape(3,3)
            np.testing.assert_allclose(observed_mass,report['config']['mass_kg'],atol=1e-6)
            np.testing.assert_allclose(observed_inertia,np.diag(report['config']['inertia_kgm2']),atol=1e-8,rtol=1e-5)
            report['observed_physx_mass_kg']=observed_mass
            report['observed_physx_inertia_kgm2']=observed_inertia.tolist()
            body.set_world_poses(positions=np.array([[0.,0.,3.]],np.float32),orientations=np.array([[1.,0.,0.,0.]],np.float32))
            body.set_linear_velocities(np.zeros((1,3),np.float32));body.set_angular_velocities(np.zeros((1,3),np.float32))
            model=Quadrotor(report['config']);acceleration=np.zeros(3);last_velocity=np.zeros(3)
            initial_time=float(world.current_time);started=time.perf_counter();rows=[];max_contact=0.
            force=np.array([0.,0.,model.mass*model.gravity]);desired=np.eye(3)
            for k in range(round(10/dt)):
                t=k*dt;p,q,rotation,velocity,rates=read_state(body)
                contact=np.asarray(body.get_net_contact_forces(dt=dt),float).reshape(-1,3)[0]
                max_contact=max(max_contact,float(np.linalg.norm(contact)))
                if not np.isfinite(np.r_[p,q,velocity,rates]).all():raise ValueError('PhysX state became non-finite')
                if k:acceleration=(velocity-last_velocity)/dt
                last_velocity=velocity.copy();reference=circle_reference(t,speed)
                if k%5==0:force,desired=model.outer(p,velocity,acceleration,reference)
                fw,tw,debug=model.step_wrench(rotation,rates,velocity,force,desired,dt)
                if k%5==0:
                    rows.append([t,*p,*velocity,*q,*reference['position'],*reference['velocity'],
                                 float(debug['saturated']),debug['collective_thrust_N'],*debug['rpm']])
                body.apply_forces_and_torques_at_pos(fw[None].astype(np.float32),tw[None].astype(np.float32),is_global=True)
                world.step(render=False)
            wall=time.perf_counter()-started;data=np.asarray(rows)
            np.save(output/f'speed_{int(speed):02d}.npy',data)
            errors=np.linalg.norm(data[:,1:4]-data[:,11:14],axis=1);measured=np.linalg.norm(data[:,4:7],axis=1)
            steady=float(measured[data[:,0]>=5.].mean())
            case={'target_mps':speed,'tracking_rmse_m':float(np.sqrt(np.mean(errors**2))),
                  'tracking_max_error_m':float(errors.max()),'steady_mean_speed_mps':steady,
                  'saturation_fraction':float(data[:,17].mean()),'wall_s':wall,'real_time_factor':10/wall,
                  'physics_clock_error_s':float(world.current_time)-initial_time-10.,'samples':len(data)}
            case['max_physical_contact_force_N']=max_contact
            case['passed']=bool(case['tracking_rmse_m']<.5 and case['tracking_max_error_m']<1.
                and case['saturation_fraction']<.05 and (steady<.05 if speed==0 else steady>.9*speed)
                and abs(case['physics_clock_error_s'])<1e-3 and max_contact<1e-5)
            report['cases'].append(case);(output/'result.json').write_text(json.dumps(report,indent=2))
            print('PHYSX_CONTROL '+json.dumps(case),flush=True)
        report['status']='passed' if all(c['passed'] for c in report['cases']) else 'failed'
    except Exception:
        report.update(status='failed',traceback=traceback.format_exc());print(report['traceback'],flush=True)
    finally:
        if report['status']=='running':report.update(status='interrupted',reason='Bootstrap or execution ended before final verdict')
        (output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        if app is not None:app.close()
    return 0 if report['status']=='passed' else 2


if __name__=='__main__':raise SystemExit(main())
