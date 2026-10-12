"""Original Fast-Planner SO3/mixer formulas with explicit common vehicle config.

Rigid-body integration belongs to PhysX. CPU integration is a diagnostic only.
Rotor lag is integrated analytically and its mean squared RPM supplies each
physics step's average wrench. No acceleration or velocity is set in flight.
"""
from pathlib import Path
import json
import numpy as np

ROOT=Path(__file__).resolve().parents[2]


class Quadrotor:
    def __init__(self,config=None):
        self.config=config or json.loads((ROOT/'configs/unified_quad.json').read_text())
        c=self.config;self.mass=c['mass_kg'];self.gravity=c['gravity_mps2']
        self.inertia=np.array(c['inertia_kgm2']);self.kf=c['thrust_coefficient_N_per_rpm2']
        self.km=self.kf*c['moment_to_thrust_ratio_m'];self.arm=c['arm_length_m']
        self.kp=np.array(c['position_gains']);self.kv=np.array(c['velocity_gains'])
        self.kr=np.array(c['attitude_gains']);self.kw=np.array(c['angular_rate_gains'])
        self.rpm=np.full(4,np.sqrt(self.mass*self.gravity/(4*self.kf)))

    def outer(self,position,velocity,acceleration,reference):
        ep=reference['position']-position;ev=reference['velocity']-velocity
        ea=reference['acceleration']-acceleration
        total=ep+ev+ea
        ka=np.where(np.abs(total)>3,0.,np.abs(total)*.2)
        feedback=self.kp*ep+self.kv*ev+self.mass*reference['acceleration']+self.mass*ka*ea
        force=feedback+np.array([0.,0.,self.mass*self.gravity])
        # Upstream actual theta is pi/2, despite its stale "45 degree" comment.
        cosine=np.cos(np.pi/2)
        norm=np.linalg.norm(force)
        if norm>1e-12 and force[2]/norm<cosine:
            a=cosine**2*np.dot(feedback,feedback)-feedback[2]**2
            b=2*(cosine**2-1)*feedback[2]*self.mass*self.gravity
            c=(cosine**2-1)*(self.mass*self.gravity)**2
            scale=(-b+np.sqrt(max(0.,b*b-4*a*c)))/(2*a)
            force=scale*feedback+np.array([0.,0.,self.mass*self.gravity])
        b3=force/max(np.linalg.norm(force),1e-12) if np.linalg.norm(force)>1e-6 else np.array([0.,0.,1.])
        yaw=reference['yaw'];b1d=np.array([np.cos(yaw),np.sin(yaw),0.])
        b2=np.cross(b3,b1d);b2/=max(np.linalg.norm(b2),1e-12)
        b1=np.cross(b2,b3);b1/=max(np.linalg.norm(b1),1e-12)
        desired=np.column_stack([b1,b2,b3])
        if not np.isfinite(desired).all():raise ValueError('Invalid SO3 control orientation')
        return force,desired

    def step_wrench(self,rotation,body_rates,world_velocity,force,desired,dt):
        error_matrix=desired.T@rotation-rotation.T@desired
        attitude_error=.5*np.array([error_matrix[2,1],error_matrix[0,2],error_matrix[1,0]])
        moment=-self.kr*attitude_error-self.kw*body_rates+np.cross(body_rates,self.inertia*body_rates)
        psi=.5*(3-np.trace(desired.T@rotation))
        thrust=float(force@rotation[:,2]) if psi<1. else 0.
        squared=np.array([thrust/(4*self.kf)-moment[1]/(2*self.arm*self.kf)+moment[2]/(4*self.km),
                          thrust/(4*self.kf)+moment[1]/(2*self.arm*self.kf)+moment[2]/(4*self.km),
                          thrust/(4*self.kf)+moment[0]/(2*self.arm*self.kf)-moment[2]/(4*self.km),
                          thrust/(4*self.kf)-moment[0]/(2*self.arm*self.kf)-moment[2]/(4*self.km)])
        raw=np.sqrt(np.maximum(squared,0.));lo,hi=self.config['rpm_limits'];target=np.clip(raw,lo,hi)
        saturated=bool(np.any(raw<lo)|np.any(raw>hi))
        tau=self.config['motor_time_constant_s'];decay=np.exp(-dt/tau);difference=self.rpm-target
        mean_square=target**2+2*target*difference*(tau/dt)*(1-decay)+difference**2*(tau/(2*dt))*(1-decay**2)
        self.rpm=target+difference*decay
        collective=self.kf*mean_square.sum()
        torque=np.array([self.kf*(mean_square[2]-mean_square[3])*self.arm,
                         self.kf*(mean_square[1]-mean_square[0])*self.arm,
                         self.km*(mean_square[0]+mean_square[1]-mean_square[2]-mean_square[3])])
        drag=-self.config['quadratic_drag_coefficient']*np.linalg.norm(world_velocity)*world_velocity
        return rotation[:,2]*collective+drag,rotation@torque,{
            'rpm':self.rpm.copy(),'command_rpm':target,'saturated':saturated,'collective_thrust_N':collective,'attitude_error':float(np.linalg.norm(attitude_error))}


def circle_reference(t,speed,radius=8.,ramp=4.):
    """Smooth acceleration from rest, then constant-speed curve at up to10m/s."""
    omega=speed/radius
    if t<ramp:
        rate=.5*omega*(1-np.cos(np.pi*t/ramp))
        acceleration=.5*omega*np.pi/ramp*np.sin(np.pi*t/ramp)
        angle=.5*omega*(t-ramp/np.pi*np.sin(np.pi*t/ramp))
    else:rate=omega;acceleration=0.;angle=.5*omega*ramp+omega*(t-ramp)
    cs,sn=np.cos(angle),np.sin(angle)
    return {'position':np.array([radius*sn,radius*(1-cs),3.]),
            'velocity':radius*rate*np.array([cs,sn,0.]),
            'acceleration':radius*(acceleration*np.array([cs,sn,0.])+rate**2*np.array([-sn,cs,0.])),
            'yaw':angle,'yaw_rate':rate}
