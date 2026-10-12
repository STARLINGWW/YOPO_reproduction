"""Windows-native static depth -> official YOPO probe, not a flight test."""
from pathlib import Path
import json
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/isaac_depth_probe"
OUTPUT.mkdir(parents=True, exist_ok=True)
from isaacsim import SimulationApp

app = SimulationApp({"headless": True, "enable_cameras": True, "width": 320, "height": 180})
try:
    import omni.usd
    import omni.replicator.core as rep
    from pxr import Gf, UsdGeom
    from isaacsim.core.api import World
    import cv2
    import torch

    omni.usd.get_context().new_stage()
    stage = omni.usd.get_context().get_stage()
    world = World(stage_units_in_meters=1.0)

    def box(name, position, scale):
        cube = UsdGeom.Cube.Define(stage, "/World/" + name)
        cube.CreateSizeAttr(1.0)
        xf = UsdGeom.Xformable(cube)
        xf.AddTranslateOp().Set(Gf.Vec3d(*position))
        xf.AddScaleOp().Set(Gf.Vec3d(*scale))

    box("Wall", (5., 0., 2.), (0.1, 20., 20.))
    cam = rep.create.camera(position=(0., 0., 2.), look_at=(5., 0., 2.),
                            focal_length=18., horizontal_aperture=36.,
                            clipping_range=(0.04, 20.))
    product = rep.create.render_product(cam, (160, 90))
    annotator = rep.AnnotatorRegistry.get_annotator("distance_to_image_plane")
    annotator.attach(product)
    world.reset()
    for _ in range(40):
        app.update()
        rep.orchestrator.step(rt_subframes=1)
    depth = np.asarray(annotator.get_data(), dtype=np.float32).reshape(90, 160)
    wall_median = float(np.median(depth[10:-10, 10:-10]))
    assert abs(wall_median - 4.95) < 0.05, (wall_median, "wall depth mismatch")
    box("Obstacle", (3., 0.9, 2.), (0.6, 0.8, 2.))
    times = []
    for _ in range(30):
        started = time.perf_counter()
        app.update()
        rep.orchestrator.step(rt_subframes=1)
        depth = np.asarray(annotator.get_data(), dtype=np.float32).reshape(90, 160).copy()
        times.append(time.perf_counter() - started)
    assert np.isfinite(depth).all()
    np.save(OUTPUT / "depth_m.npy", depth)
    normalized = np.clip(depth / 20., 0., 1.)
    cv2.imwrite(str(OUTPUT / "depth16.png"), np.rint(normalized * 65535).astype(np.uint16))
    color = cv2.applyColorMap(np.uint8(np.clip(depth / 6., 0., 1.) * 255), cv2.COLORMAP_TURBO)
    cv2.imwrite(str(OUTPUT / "depth_preview.png"), cv2.resize(color, (960, 540), interpolation=cv2.INTER_NEAREST))
    sys.path.insert(0, str(ROOT / "external/audit_sources/YOPO-Simple/YOPO"))
    from config.config import cfg
    cfg["train"] = False
    from policy.yopo_network import YopoNetwork
    model = YopoNetwork().cuda().eval()
    weights = ROOT / "external/audit_sources/YOPO-Simple/YOPO/saved/YOPO_1/epoch50.pth"
    model.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True), strict=True)
    # Match the stock online node's resize and 8-bit inpaint preprocessing.
    resized = cv2.resize(normalized, (160, 96), interpolation=cv2.INTER_NEAREST)
    invalid = np.isnan(resized) | (resized < 0.04 / 20.)
    processed = cv2.inpaint(np.uint8(resized * 255), np.uint8(invalid), 1, cv2.INPAINT_NS).astype(np.float32) / 255.
    with torch.inference_mode():
        endstate, scores = model.inference(
            torch.from_numpy(processed[None, None]).cuda(),
            torch.tensor([[1., 0., 0., 0., 0., 0., 10., 0., 0.]], device="cuda"))
    assert torch.isfinite(endstate).all() and torch.isfinite(scores).all()
    result = {
        "scope": "static Isaac depth + official YOPO inference; no dynamics or closed-loop flight",
        "wall_expected_depth_m": 4.95,
        "wall_measured_median_m": wall_median,
        "sensor_resolution_wh": [160, 90],
        "depth_range_m": [float(depth.min()), float(depth.max())],
        "render_readback_samples": 30,
        "render_readback_p50_ms": float(np.median(times) * 1000),
        "render_readback_p95_ms": float(np.percentile(times, 95) * 1000),
        "network_output_finite": True,
        "endstate_shape": list(endstate.shape),
        "score_shape": list(scores.shape),
        "scores": scores.cpu().numpy().tolist(),
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("YOPO_DEPTH_PROBE " + json.dumps(result), flush=True)
except Exception:
    import traceback
    failure = traceback.format_exc()
    (OUTPUT / "failure.txt").write_text(failure, encoding="utf-8")
    print(failure, flush=True)
    raise
finally:
    app.close()
