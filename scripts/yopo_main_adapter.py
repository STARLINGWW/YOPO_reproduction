"""Host-side adapter for the main-branch YOPO policy, used by run_navigation.py.

The released official weights come from the YOPO-Simple branch and the locally
trained weights from the main branch; the two networks are the same tensors with
seven renamed keys (verified in artifacts/expert/official_checkpoint_mapping.json).
This adapter always uses the main-branch network and the main-branch runtime
configuration (configs/paper_aligned.json + the main traj_opt.yaml), so an A/B run
differs in the weights file only. Inference mirrors the frozen ROS2 planner
(ros2_ws/src/yopo_runtime/yopo_runtime/main_planner.py) exactly: 160x90 metre depth
rescaled to 160x96 and divided by 20, body-frame speed/acceleration plus the
body-frame goal direction as the 9-dim observation, argmin over the 15 predicted
scores, selected primitive decoded to three world-frame end states and tracked with
a quintic polynomial.
"""
from pathlib import Path
import hashlib
import sys
import time
import cv2
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from yopo_repro.policy import build_policy,prepare_observation
from yopo_repro.quintic import Quintic
from flightpolicy.yopo.primitive_utils import LatticeParam,LatticePrimitive,calculate_yaw


class Planner:
    def __init__(self,start,goal,speed=1.5,weights=None,device='cuda'):
        torch.backends.cuda.matmul.allow_tf32 = False
        self.policy,self.profile,cfg = build_policy(device)
        self.weights = Path(weights).resolve() if weights else None
        if self.weights is None:
            raise ValueError('Explicit weights path required for the A/B demo')
        state = torch.load(self.weights,map_location=device,weights_only=True)
        self.policy.load_state_dict(state,strict=True)
        self.policy.eval()
        inference_cfg = dict(cfg);inference_cfg['vel_max'] = float(speed)
        self.policy.lattice_space = LatticeParam(inference_cfg)
        self.policy.lattice_primitive = LatticePrimitive(self.policy.lattice_space)
        self.duration = self.policy.lattice_space.segment_time
        self.checkpoint_sha256 = hashlib.sha256(self.weights.read_bytes()).hexdigest()
        self.device = torch.device(device)
        self.goal = np.asarray(goal,dtype=float)
        self.p = np.asarray(start,dtype=float).copy()
        self.v = np.zeros(3);self.a = np.zeros(3);self.yaw = 0.
        self.poly = None;self.plan_time = 0.;self.last = None
        self.selected_id = -1;self.selected_score = 0.
        self.predictions = np.zeros((15,25,3));self.scores = np.zeros(15)

    @torch.inference_mode()
    def update(self,depth_m,rotation_wc,sim_time):
        started = time.perf_counter()
        depth = np.minimum(np.nan_to_num(np.asarray(depth_m,dtype=np.float32),nan=20.,posinf=20.,neginf=0.),20.)/20.
        depth = cv2.resize(depth,(160,96),interpolation=cv2.INTER_LINEAR)
        rotation = np.asarray(rotation_wc,dtype=float)
        if self.last is not None and self.last[0]<=sim_time<self.last[0]+self.last[1].duration:
            previous = self.last[1];t = sim_time-self.last[0]
            start = np.column_stack([previous.evaluate(t),previous.evaluate(t,1),previous.evaluate(t,2)])
        else:
            start = np.column_stack([self.p,self.v,self.a])
        delta = self.goal-start[:,0];direction = delta/max(np.linalg.norm(delta),1e-8)
        obs = np.r_[rotation.T@start[:,1],rotation.T@start[:,2],rotation.T@direction].astype(np.float32)[None]
        prepared = prepare_observation(obs,self.policy)
        output = self.policy(torch.from_numpy(depth[None,None]).to(self.device),
                             torch.from_numpy(prepared).to(self.device))
        scores = output[0,9].reshape(15).detach().cpu().numpy()
        selected = int(np.argmin(scores))
        raw = output[:,:9].reshape(1,9,15)[:,:,selected]
        body = self.policy.pred_to_endstate(raw,14-selected).detach().cpu().numpy().reshape(3,3)
        end = rotation@body;end[:,0] += start[:,0]
        self.poly = Quintic(start,end,self.duration)
        self.last = (sim_time,self.poly)
        sample_t = np.linspace(0.,self.duration,25)
        predictions = np.zeros((15,25,3))
        for index in range(15):
            raw_i = output[:,:9].reshape(1,9,15)[:,:,index]
            decoded = self.policy.pred_to_endstate(raw_i,14-index).detach().cpu().numpy().reshape(3,3)
            world = rotation@decoded;world[:,0] += start[:,0]
            polynomial = Quintic(start,world,self.duration)
            predictions[index] = polynomial.evaluate(sample_t)
        self.predictions = predictions
        self.scores = scores
        self.selected_id = selected
        self.selected_score = float(scores[selected])
        self.plan_time = sim_time
        return (time.perf_counter()-started)*1000.

    def reference(self,sim_time,dt):
        if self.poly is not None:
            t = float(np.clip(sim_time-self.plan_time,0.,self.poly.duration))
            self.p = np.asarray(self.poly.evaluate(t))
            self.v = np.asarray(self.poly.evaluate(t,1))
            self.a = np.asarray(self.poly.evaluate(t,2))
            self.yaw,_ = calculate_yaw(self.v,self.goal-self.p,self.yaw,dt)
        return {'position':self.p.copy(),'velocity':self.v.copy(),'acceleration':self.a.copy(),'yaw':self.yaw}
