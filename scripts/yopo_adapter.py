"""ROS-free adapter preserving the pinned YOPO-Simple planning equations."""
from pathlib import Path
import sys
import time
import numpy as np
import cv2
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "external/audit_sources/YOPO-Simple/YOPO"))
from config.config import cfg


class Planner:
    def __init__(self, start, goal, speed=1.5, weights=None):
        cfg["train"] = False
        cfg["velocity"] = speed
        from policy.yopo_network import YopoNetwork
        from policy.poly_solver import Poly5Solver, calculate_yaw
        self.solver = Poly5Solver
        self.calculate_yaw = calculate_yaw
        self.net = YopoNetwork().cuda().eval()
        weights = Path(weights) if weights else ROOT / "external/audit_sources/YOPO-Simple/YOPO/saved/YOPO_1/epoch50.pth"
        weights = weights if weights.is_absolute() else ROOT / weights
        self.net.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True), strict=True)
        self.transform = self.net.state_transform
        self.lattice = self.transform.lattice_primitive
        self.duration = self.lattice.segment_time
        self.goal = np.asarray(goal, dtype=float)
        self.p = np.asarray(start, dtype=float).copy()
        self.v = np.zeros(3)
        self.a = np.zeros(3)
        self.yaw = 0.
        self.poly = None
        self.plan_time = 0.
        self.selected_id = -1
        self.selected_score = 0.
        self.predictions = None
        self.scores = None

    @torch.inference_mode()
    def update(self, depth_m, rotation_wc, sim_time):
        started = time.perf_counter()
        depth = cv2.resize(depth_m, (160, 96), interpolation=cv2.INTER_NEAREST)
        depth = np.minimum(depth, 20.) / 20.
        mask = ~np.isfinite(depth) | (depth < 0.04 / 20.)
        depth = np.nan_to_num(depth, nan=0., posinf=1., neginf=0.)
        depth = cv2.inpaint(np.uint8(np.clip(depth, 0., 1.) * 255), np.uint8(mask), 1, cv2.INPAINT_NS).astype(np.float32) / 255.
        obs = np.concatenate([rotation_wc.T @ self.v, rotation_wc.T @ self.a,
                              rotation_wc.T @ (self.goal - self.p)]).astype(np.float32)[None]
        prepared = self.transform.prepare_input_cpu(self.transform.normalize_obs_cpu(obs))
        pred, score = self.net(torch.from_numpy(depth[None, None]).cuda(), torch.from_numpy(prepared).cuda())
        pred = pred.cpu().numpy().reshape(9, -1).T
        score = score.cpu().numpy().reshape(-1)
        assert np.isfinite(pred).all() and np.isfinite(score).all()
        decoded = self.transform.pred_to_endstate_cpu(pred, np.arange(self.lattice.traj_num - 1, -1, -1))
        world = np.matmul(rotation_wc, decoded.reshape(-1, 3, 3).transpose(0, 2, 1))
        index = int(np.argmin(score))
        all_poly = [[self.solver(self.p[j], self.v[j], self.a[j], self.p[j] + world[i, j, 0],
                                world[i, j, 1], world[i, j, 2], self.duration) for j in range(3)]
                    for i in range(len(score))]
        self.poly = all_poly[index]
        self.plan_time = sim_time
        sample_t = np.linspace(0., self.duration, 25)
        self.predictions = np.asarray([[axis.get_position(sample_t) for axis in traj] for traj in all_poly]).transpose(0, 2, 1)
        self.scores = score
        self.selected_id, self.selected_score = index, float(score[index])
        return (time.perf_counter() - started) * 1000.

    def reference(self, sim_time, dt):
        if self.poly is not None:
            t = float(np.clip(sim_time - self.plan_time, 0., self.duration))
            self.p = np.array([axis.get_position(t) for axis in self.poly])
            self.v = np.array([axis.get_velocity(t) for axis in self.poly])
            self.a = np.array([axis.get_acceleration(t) for axis in self.poly])
            self.yaw, _ = self.calculate_yaw(self.v, self.goal - self.p, self.yaw, dt)
        return {"position": self.p.copy(), "velocity": self.v.copy(),
                "acceleration": self.a.copy(), "yaw": self.yaw}
