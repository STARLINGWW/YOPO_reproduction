"""Agile Autonomy official network + unchanged C++ polynomial/arc-length core.

ROS2/Isaac equivalent experiment: common depth/odometry/controller boundary.
Original body-frame scores, mode filtering, reference continuity and speed ramp.
No expert fallback and no map truth. First task starts with zero jerk explicitly.
"""
from pathlib import Path
from types import SimpleNamespace
import ctypes
import hashlib
import importlib.util
import json
import sys
import time
import cv2
import numpy as np
from scipy.spatial.transform import Rotation
from geometry_msgs.msg import Transform,Twist
from trajectory_msgs.msg import MultiDOFJointTrajectory,MultiDOFJointTrajectoryPoint

ROOT=Path('/workspace')


def xyz(target,value):target.x,target.y,target.z=map(float,value)


class AgilePlanner:
    def __init__(self,speed=6.,engine='tensorflow',device='cpu'):
        self.engine=engine;self.device=device
        parity=json.loads((ROOT/'artifacts/agile_autonomy/tf24_tf215_parity.json').read_text())
        if parity['status']!='passed' or not parity['ordered_network_weight_arrays_bitwise_equal']:
            raise ValueError('Agile framework parity gate not passed')
        reference=json.loads((ROOT/'artifacts/agile_autonomy/tf215_probe.json').read_text())
        self.checkpoint_sha256=hashlib.sha256(json.dumps(reference['checkpoint_files'],sort_keys=True).encode()).hexdigest()
        if engine=='tensorflow':
            if device!='cpu':raise ValueError('Legacy TensorFlow backend is validated on CPU only')
            import tensorflow as tf
            tf.config.set_visible_devices([], 'GPU')
            config=SimpleNamespace(img_height=224,img_width=224,use_rgb=False,use_depth=True,
                freeze_backbone=False,modes=3,predict_state_number=[],out_seq_len=10,state_dim=3,
                seq_len=1,use_position=False,use_attitude=True)
            spec=importlib.util.spec_from_file_location('agile_ros2_nets',ROOT/'vendor/agile_ros2/nets.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            self.network=module.create_network(config)
            self.network({'depth':np.zeros((1,1,224,224,3),np.float32),'imu':np.zeros((1,1,21),np.float32)},training=False)
            checkpoint=ROOT/'external/agile_autonomy/planner_learning/models/ckpt-50'
            restored=tf.train.Checkpoint(net=self.network).restore(str(checkpoint))
            restored.assert_existing_objects_matched();restored.expect_partial()
            if [hashlib.sha256(w.numpy().tobytes()).hexdigest() for w in self.network.weights]!=reference['ordered_weight_sha256']:
                raise ValueError('Checkpoint does not match validated network')
            self._predict=lambda depth,imu:self.network({'depth':depth,'imu':imu},training=False).numpy()
        elif engine=='torch':
            import torch
            sys.path.insert(0,str(ROOT/'src'))
            from agile_runtime.torch_network import AgileNetwork
            export=ROOT/'artifacts/agile_autonomy/torch_export_v1'
            gate=json.loads((export/f'torch_{device}_parity.json').read_text())
            if gate['status']!='passed' or gate['original_tf24_comparison']['status']!='passed' or gate['checkpoint_sha256']!=self.checkpoint_sha256:
                raise ValueError('Requested PyTorch device has not passed original TF2.4 parity')
            torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
            self.network=AgileNetwork(export).to(device).eval()
            if self.network.manifest['source_checkpoint_sha256']!=self.checkpoint_sha256:raise ValueError('Converted checkpoint identity mismatch')
            def predict(depth,imu):
                with torch.inference_mode():
                    return self.network(torch.from_numpy(depth).to(device),torch.from_numpy(imu).to(device)).cpu().numpy()
            self._predict=predict
        else:raise ValueError('Unknown Agile inference engine')
        self.lib=ctypes.CDLL(str(ROOT/'ros2_ws/install/yopo_agile_core/lib/libagile_trajectory.so'))
        pointer=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
        self.lib.agile_fit.argtypes=[pointer,pointer,ctypes.c_double,pointer,pointer]
        self.lib.agile_fit.restype=ctypes.c_int
        self.speed=float(speed);self.last=None;self.last_debug={}

    def reset(self,episode):self.last=None

    def __call__(self,observation,goal):
        started=time.perf_counter();image=observation.depth;odom=observation.odometry
        if image.encoding!='32FC1' or (image.width,image.height)!=(160,90):raise ValueError('Unexpected depth contract')
        if image.step<640 or len(image.data)<image.step*90:raise ValueError('Malformed image')
        depth=np.ndarray((90,160),dtype='>f4' if image.is_bigendian else '<f4',buffer=bytes(image.data),strides=(image.step,4)).astype(np.float32)
        # Original input was millimetres, clipped20000 and divided80.
        depth=np.clip(np.nan_to_num(depth,nan=20.,posinf=20.,neginf=0.),0.,20.)*12.5
        depth=np.repeat(cv2.resize(depth,(224,224),interpolation=cv2.INTER_LINEAR)[...,None],3,axis=-1)
        p=odom.pose.pose.position;p=np.array([p.x,p.y,p.z])
        q=odom.pose.pose.orientation;rotation=Rotation.from_quat([q.x,q.y,q.z,q.w]).as_matrix()
        if odom.child_frame_id!=f'e{observation.episode_id}/base_link':raise ValueError('Expected body-frame odometry twist')
        vb=odom.twist.twist.linear;vb=np.array([vb.x,vb.y,vb.z]);vw=rotation@vb
        wb=odom.twist.twist.angular;wb=np.array([wb.x,wb.y,wb.z])
        gp=goal.pose.position;direction=np.array([gp.x,gp.y,gp.z])-p
        direction/=max(np.linalg.norm(direction),1e-9)
        imu=np.r_[p,rotation.reshape(-1),vb,wb,rotation.T@direction].astype(np.float32)
        raw=self._predict(depth[None,None],imu[None,None])[0]
        order=np.abs(raw[:,0]).argsort();raw=raw[order];scores=np.abs(raw[:,0])
        accepted=[i for i in range(3) if i==0 or (scores[0]/scores[i] if scores[i]>0 else (np.inf if scores[0]>0 else 0))>.9]
        candidates=np.stack([(rotation@raw[i,1:].reshape(3,10)).T+p for i in accepted])
        candidates[:,:,2]=np.clip(candidates[:,:,2],1.,30.)
        now=observation.stamp_ns*1e-9
        initial=np.zeros((4,3));initial[0]=p;initial[1]=vw;selected=0
        if self.last is not None:
            previous_time,points=self.last
            shift=max(0.,now-previous_time)
            aligned=np.stack([np.interp(points[:,0]+shift,points[:,0],points[:,k]) for k in range(1,4)],axis=-1)
            costs=np.linalg.norm(candidates-aligned,axis=-1).sum(axis=-1);selected=int(costs.argmin())
            initial[2]=[np.interp(shift,points[:,0],points[:,k]) for k in range(7,10)]
            initial[3]=[np.interp(shift,points[:,0],points[:,k]) for k in range(10,13)]
        coefficients=np.empty((6,3),np.float64);points=np.empty((10,21),np.float64)
        result=self.lib.agile_fit(np.ascontiguousarray(candidates[selected],dtype=np.float64),initial,
                                  min(np.linalg.norm(vw)+1.,self.speed),coefficients,points)
        if result<0 or not np.isfinite(points).all():raise RuntimeError(f'Original Agile trajectory core failed: {result}')
        self.last=(now,points.copy())
        message=MultiDOFJointTrajectory();message.header.stamp=image.header.stamp
        message.header.frame_id=f'e{observation.episode_id}/world';message.joint_names=['quadrotor']
        for row in points:
            point=MultiDOFJointTrajectoryPoint();transform=Transform();xyz(transform.translation,row[1:4])
            transform.rotation.w,transform.rotation.x,transform.rotation.y,transform.rotation.z=map(float,row[13:17])
            velocity=Twist();xyz(velocity.linear,row[4:7])
            acceleration=Twist();xyz(acceleration.linear,row[7:10])
            point.transforms=[transform];point.velocities=[velocity];point.accelerations=[acceleration]
            ns=int(round(row[0]*1e9));point.time_from_start.sec=ns//1_000_000_000;point.time_from_start.nanosec=ns%1_000_000_000
            message.points.append(point)
        self.last_debug={'baseline':'Agile Autonomy official ckpt-50','engine':self.engine,'device':self.device,'selected_original_mode':int(order[accepted[selected]]),
            'scores':scores.tolist(),'accepted_modes':accepted,'arc_length_adapted':bool(result),
            'planning_wall_ms':(time.perf_counter()-started)*1000,'checkpoint_sha256':self.checkpoint_sha256,
            'scope':'ROS2/Isaac equivalent, common sensor/controller; original network and numerical trajectory core'}
        return message
