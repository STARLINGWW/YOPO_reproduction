"""Self-trained original-main policy exposed as a standard ROS2 trajectory.

Contract: pose is in eN/world, odometry twist in eN/base_link (ROS convention),
depth is 160x90 optical-Z metres with the trained camera aligned to body FLU.
This class has no map interface. Reference-state replanning matches the original
position-control integration. Episode reset clears all trajectory state.
"""
from pathlib import Path
import hashlib
import json
import math
import sys
import time
import numpy as np
import torch
import cv2
from scipy.spatial.transform import Rotation
from geometry_msgs.msg import Transform,Twist
from trajectory_msgs.msg import MultiDOFJointTrajectory,MultiDOFJointTrajectoryPoint

ROOT=Path('/workspace')
sys.path.insert(0,str(ROOT/'src'))
from yopo_repro.policy import build_policy,prepare_observation
from yopo_repro.quintic import Quintic
from flightpolicy.yopo.primitive_utils import LatticeParam,LatticePrimitive,calculate_yaw
from .protocol_node import stamp_ns


def assign_xyz(target,values):
    target.x=float(values[0]);target.y=float(values[1]);target.z=float(values[2])


class MainPlanner:
    def __init__(self,checkpoint,speed=6.,device='cuda'):
        torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
        checkpoint=Path(checkpoint).resolve()
        if not checkpoint.is_relative_to(ROOT/'checkpoints'):raise ValueError('This runtime accepts locally trained checkpoints only')
        manifest=json.loads((checkpoint.parent/'run_manifest.json').read_text(encoding='utf-8'))
        if not manifest.get('initialization','').startswith('random entire network'):raise ValueError('Checkpoint lacks scratch initialization provenance')
        self.policy,self.profile,cfg=build_policy(device)
        if manifest['profile']!=self.profile or manifest['trajectory']!=cfg:raise ValueError('Checkpoint profile/config differs from runtime')
        self.policy.load_state_dict(torch.load(checkpoint,map_location=device,weights_only=True),strict=True)
        self.policy.eval();self.device=torch.device(device)
        inference_cfg=dict(cfg);inference_cfg['vel_max']=float(speed)
        self.policy.lattice_space=LatticeParam(inference_cfg)
        self.policy.lattice_primitive=LatticePrimitive(self.policy.lattice_space)
        self.duration=self.policy.lattice_space.segment_time
        self.checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        self.last=None;self.episode=None;self.last_debug={}

    def reset(self,episode):self.last=None;self.episode=episode

    @torch.inference_mode()
    def __call__(self,observation,goal):
        started=time.perf_counter()
        image=observation.depth;odom=observation.odometry
        if image.encoding!='32FC1' or (image.width,image.height)!=(160,90):raise ValueError('Expected trained 160x90 metre depth')
        if image.step<image.width*4 or len(image.data)<image.step*image.height:raise ValueError('Malformed depth buffer')
        if odom.child_frame_id!=f'e{observation.episode_id}/base_link':raise ValueError('Odometry twist must be body-frame')
        depth=np.ndarray((image.height,image.width),dtype='>f4' if image.is_bigendian else '<f4',buffer=bytes(image.data),strides=(image.step,4)).astype(np.float32)
        depth=np.minimum(np.nan_to_num(depth,nan=20.,posinf=20.,neginf=0.),20.)/20.
        depth=cv2.resize(depth,(160,96),interpolation=cv2.INTER_LINEAR)
        p=np.array([odom.pose.pose.position.x,odom.pose.pose.position.y,odom.pose.pose.position.z])
        q=odom.pose.pose.orientation
        rotation=Rotation.from_quat([q.x,q.y,q.z,q.w]).as_matrix()
        vb=odom.twist.twist.linear
        vw=rotation@np.array([vb.x,vb.y,vb.z])
        now=observation.stamp_ns*1e-9
        if self.last is not None and self.last[0]<=now<self.last[0]+self.last[1].duration:
            previous=self.last[1];t=now-self.last[0]
            start=np.column_stack([previous.evaluate(t),previous.evaluate(t,1),previous.evaluate(t,2)])
        else:start=np.column_stack([p,vw,np.zeros(3)])
        gp=goal.pose.position;goal_w=np.array([gp.x,gp.y,gp.z])
        delta=goal_w-start[:,0];direction=delta/max(np.linalg.norm(delta),1e-8)
        obs=np.r_[rotation.T@start[:,1],rotation.T@start[:,2],rotation.T@direction].astype(np.float32)[None]
        prepared=prepare_observation(obs,self.policy)
        output=self.policy(torch.from_numpy(depth[None,None]).to(self.device),torch.from_numpy(prepared).to(self.device))
        scores=output[0,9].reshape(15).cpu().numpy()
        selected=int(np.argmin(scores))
        raw=output[:,:9].reshape(1,9,15)[:,:,selected]
        body=self.policy.pred_to_endstate(raw,14-selected).cpu().numpy().reshape(3,3)
        end=rotation@body;end[:,0]+=start[:,0]
        polynomial=Quintic(start,end,self.duration)
        self.last=(now,polynomial)
        message=MultiDOFJointTrajectory();message.header.stamp=image.header.stamp
        message.header.frame_id=f'e{observation.episode_id}/world';message.joint_names=['quadrotor']
        yaw=math.atan2(rotation[1,0],rotation[0,0]);dt=self.duration/20
        for i,t in enumerate(np.linspace(0,self.duration,21)):
            position=polynomial.evaluate(t);velocity=polynomial.evaluate(t,1);acceleration=polynomial.evaluate(t,2)
            yaw_rate=0.
            if i:yaw,yaw_rate=calculate_yaw(velocity,goal_w-position,yaw,dt)
            transform=Transform();assign_xyz(transform.translation,position)
            transform.rotation.z=math.sin(yaw/2);transform.rotation.w=math.cos(yaw/2)
            vel=Twist();assign_xyz(vel.linear,velocity);vel.angular.z=float(yaw_rate)
            acc=Twist();assign_xyz(acc.linear,acceleration)
            point=MultiDOFJointTrajectoryPoint();point.transforms=[transform];point.velocities=[vel];point.accelerations=[acc]
            ns=int(round(t*1e9));point.time_from_start.sec=ns//1_000_000_000;point.time_from_start.nanosec=ns%1_000_000_000
            message.points.append(point)
        self.last_debug={'checkpoint_sha256':self.checkpoint_sha256,'selected':selected,'scores':scores.tolist(),
                         'planning_wall_ms':(time.perf_counter()-started)*1000,'reference_state_replanning':True,
                         'observation_stamp_ns':observation.stamp_ns,'episode':observation.episode_id}
        return message
