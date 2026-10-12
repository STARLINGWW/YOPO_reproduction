"""Trajectory validity and measured-latency scheduling for the native simulator.

Received commands cannot benefit from a slow/frozen renderer: application starts
no earlier than acquisition simulation time plus measured wall end-to-end delay.
"""
from dataclasses import dataclass
import numpy as np
from yopo_repro.quintic import Quintic


@dataclass
class ScheduledTrajectory:
    start: float
    available: float
    times: np.ndarray
    positions: np.ndarray
    velocities: np.ndarray
    accelerations: np.ndarray
    yaw: np.ndarray
    segments: list
    latency: float
    observation_start: float

    @property
    def end(self):return self.start+float(self.times[-1])

    def sample(self,now):
        elapsed=now-self.start
        i=int(np.clip(np.searchsorted(self.times,elapsed,side='right')-1,0,len(self.times)-2))
        t=elapsed-self.times[i];dt=self.times[i+1]-self.times[i]
        return {'position':self.segments[i].evaluate(t),'velocity':self.segments[i].evaluate(t,1),
                'acceleration':self.segments[i].evaluate(t,2),'yaw':float(self.yaw[i]+t/dt*(self.yaw[i+1]-self.yaw[i])),
                'jerk':self.segments[i].evaluate(t,3),
                'yaw_rate':float((self.yaw[i+1]-self.yaw[i])/dt)}


class TrajectoryBuffer:
    def __init__(self,episode=1):
        self.episode=episode;self.pending=[];self.active=None;self.last_start=-np.inf
        self.stats={'received':0,'accepted':0,'expired_on_arrival':0,'old_result':0,'applied':0,'expired_in_control':0}

    def submit(self,start,times,positions,velocities,accelerations,yaw,receipt_sim,latency,observation_start=None):
        self.stats['received']+=1
        times=np.asarray(times,float);positions=np.asarray(positions,float);velocities=np.asarray(velocities,float)
        accelerations=np.asarray(accelerations,float);yaw=np.unwrap(np.asarray(yaw,float))
        if len(times)<2 or times[0]!=0 or not np.all(np.diff(times)>0):raise ValueError('Invalid trajectory sampling times')
        if any(v.shape!=(len(times),3) for v in [positions,velocities,accelerations]) or yaw.shape!=(len(times),):raise ValueError('Trajectory shape mismatch')
        if not all(np.isfinite(v).all() for v in [times,positions,velocities,accelerations,yaw]):raise ValueError('Non-finite trajectory')
        if latency<0 or not np.isfinite(latency):raise ValueError('Invalid measured latency')
        if start<=self.last_start:self.stats['old_result']+=1;return False
        observation_start=start if observation_start is None else float(observation_start)
        if not np.isfinite(observation_start) or observation_start>start+1e-8:raise ValueError('Observation cannot be newer than planned start state')
        available=max(receipt_sim,observation_start+latency,start)
        if available>=start+times[-1]:self.stats['expired_on_arrival']+=1;return False
        segments=[Quintic(np.column_stack([positions[i],velocities[i],accelerations[i]]),
                          np.column_stack([positions[i+1],velocities[i+1],accelerations[i+1]]),times[i+1]-times[i]) for i in range(len(times)-1)]
        self.pending.append(ScheduledTrajectory(start,available,times,positions,velocities,accelerations,yaw,segments,latency,observation_start))
        self.pending=sorted(self.pending,key=lambda v:v.start)[-8:];self.stats['accepted']+=1
        return True

    def sample(self,now):
        ready=[v for v in self.pending if v.available<=now and v.end>now and v.start>self.last_start]
        if ready:
            self.active=max(ready,key=lambda v:v.start);self.last_start=self.active.start;self.stats['applied']+=1
        self.pending=[v for v in self.pending if v.available>now and v.end>now and v.start>self.last_start]
        if self.active is not None and now>=self.active.end:
            self.active=None;self.stats['expired_in_control']+=1
        return self.active.sample(now) if self.active is not None else None

    def stop(self,at=None):
        self.pending.clear();self.active=None
        if at is not None:self.last_start=max(self.last_start,float(at))


def decode_ros_trajectory(message):
    times=[];positions=[];velocities=[];accelerations=[];yaw=[]
    for point in message.points:
        if len(point.transforms)!=1 or len(point.velocities)!=1 or len(point.accelerations)!=1:raise ValueError('Expected single-vehicle p/v/a trajectory')
        transform=point.transforms[0];p=transform.translation;v=point.velocities[0].linear;a=point.accelerations[0].linear;q=transform.rotation
        if abs(np.linalg.norm([q.w,q.x,q.y,q.z])-1)>1e-3:raise ValueError('Invalid reference quaternion')
        times.append(point.time_from_start.sec+point.time_from_start.nanosec*1e-9)
        positions.append([p.x,p.y,p.z]);velocities.append([v.x,v.y,v.z]);accelerations.append([a.x,a.y,a.z])
        yaw.append(np.arctan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z)))
    return times,positions,velocities,accelerations,yaw
