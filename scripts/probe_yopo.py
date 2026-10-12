"""Bounded feasibility probe; synthetic inputs are NOT a navigation evaluation."""
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "external/audit_sources/YOPO-Simple/YOPO"
OUTPUT = ROOT / "artifacts/probes"
OUTPUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(ROOT / "vendor/probe_deps"))

import numpy as np
import torch
from config.config import cfg
from policy.yopo_network import YopoNetwork

torch.manual_seed(0)
torch.set_num_threads(4)
cfg["train"] = False
checkpoint = SOURCE / "saved/YOPO_1/epoch50.pth"
model = YopoNetwork().cuda().eval()
state = torch.load(checkpoint, map_location="cpu", weights_only=True)
model.load_state_dict(state, strict=True)
depth = torch.full((1, 1, 96, 160), 0.5, device="cuda")
obs = torch.tensor([[2., 0., 0., 0., 0., 0., 10., 0., 0.]], device="cuda")
prepared = model.state_transform.prepare_input(model.state_transform.normalize_obs(obs.clone()))
result = {
    "scope": "official pretrained network on synthetic depth/state; no ROS or navigation validation",
    "source_commit": "bd8a7f91953cfef9f1aa9a48d7ff0ab7bceee132",
    "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
    "python": sys.version,
    "torch": torch.__version__,
    "cuda_runtime": torch.version.cuda,
    "device": torch.cuda.get_device_name(),
    "capability": torch.cuda.get_device_capability(),
    "parameters": sum(p.numel() for p in model.parameters()),
    "packages": {},
}
for package in ["numpy", "scipy", "ruamel.yaml", "open3d", "tensorboard", "rich"]:
    try:
        result["packages"][package] = metadata.version(package)
    except metadata.PackageNotFoundError:
        result["packages"][package] = None

with torch.inference_mode():
    for _ in range(30):
        model(depth, prepared)
    torch.cuda.synchronize()
    latencies = []
    torch.cuda.reset_peak_memory_stats()
    for _ in range(200):
        torch.cuda.synchronize()
        started = time.perf_counter()
        prediction, score = model(depth, prepared)
        torch.cuda.synchronize()
        latencies.append((time.perf_counter() - started) * 1000)
    endstate, transformed_score = model.inference(depth, obs.clone())
    assert torch.isfinite(endstate).all() and torch.isfinite(transformed_score).all()
    assert endstate.shape == (1, 9, 3, 5) and score.shape == (1, 3, 5)
    result["inference"] = {
        "warmup": 30, "samples": 200, "batch_size": 1, "precision": "FP32",
        "timing_scope": "synchronized wall-clock network forward only; GPU-resident inputs; no image IO/ROS/trajectory solve",
        "p50_ms": float(np.percentile(latencies, 50)),
        "p95_ms": float(np.percentile(latencies, 95)),
        "mean_ms": float(np.mean(latencies)),
        "endstate_shape": list(endstate.shape),
        "score_shape": list(score.shape),
        "finite": True,
        "peak_allocated_mib": torch.cuda.max_memory_allocated() / 2**20,
    }
print(json.dumps(result, indent=2), flush=True)
(OUTPUT / "probe_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

# One small pointcloud and artificial depth/state inputs exercise the original
# ESDF / trajectory / score losses and backward pass. This is not a training run
# or a convergence test, and its map memory is not representative of ten maps.
import open3d as o3d
fixture = OUTPUT / "synthetic_probe_data"
fixture.mkdir(exist_ok=True)
xy = np.linspace(-12, 12, 121)
x, y = np.meshgrid(xy, xy)
floor = np.column_stack([x.ravel(), y.ravel(), np.zeros(x.size)])
z = np.linspace(0, 6, 31)
wy, wz = np.meshgrid(xy, z)
wall = np.column_stack([np.full(wy.size, 10.), wy.ravel(), wz.ravel()])
cloud = o3d.geometry.PointCloud()
cloud.points = o3d.utility.Vector3dVector(np.vstack([floor, wall]))
o3d.io.write_point_cloud(str(fixture / "pointcloud-0.ply"), cloud)
cfg["dataset_path"] = str(fixture)
cfg["train"] = True
from policy.yopo_trainer import YopoTrainer
from loss.loss_function import YOPOLoss

trainer = YopoTrainer.__new__(YopoTrainer)
trainer.device = torch.device("cuda")
trainer.batch_size = 16
trainer.traj_num = cfg["traj_num"]
trainer.policy = model.train()
trainer.yopo_loss = YOPOLoss()
optimizer = torch.optim.AdamW(model.parameters(), lr=1.5e-4, fused=True)
b = 16
train_depth = torch.rand((b, 1, 96, 160), device="cuda")
pos = torch.tensor([[0., 0., 2.]], device="cuda").repeat(b, 1)
rot = torch.eye(3, device="cuda").unsqueeze(0).repeat(b, 1, 1)
train_obs = obs.repeat(b, 1)
map_id = torch.zeros(b, dtype=torch.long, device="cuda")
loss_values, step_times = [], []
torch.cuda.reset_peak_memory_stats()
for step in range(12):
    torch.cuda.synchronize()
    started = time.perf_counter()
    optimizer.zero_grad(set_to_none=True)
    losses = trainer.forward_and_compute_loss(train_depth, pos, rot, train_obs.clone(), map_id)
    loss = losses[0] + losses[1]
    assert torch.isfinite(loss)
    loss.backward()
    assert all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None)
    optimizer.step()
    torch.cuda.synchronize()
    step_times.append(time.perf_counter() - started)
    loss_values.append(float(loss.detach()))
result["synthetic_backward"] = {
    "scope": "12 optimizer steps, one small synthetic ESDF, artificial unpaired inputs; NOT convergence/navigation evidence",
    "batch_size": b, "steps": 12, "finite_loss_and_gradients": True,
    "loss_values": loss_values,
    "median_step_seconds_excluding_first_2": float(np.median(step_times[2:])),
    "peak_allocated_mib": torch.cuda.max_memory_allocated() / 2**20,
    "peak_reserved_mib": torch.cuda.max_memory_reserved() / 2**20,
    "map_shape": list(trainer.yopo_loss.safety_loss.sdf_maps[0].shape),
}
(OUTPUT / "probe_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result["synthetic_backward"], indent=2), flush=True)
