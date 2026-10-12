"""Independently recompute flight metrics and decode the delivered video."""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
import cv2
import imageio.v2 as imageio

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="forest_seed7_v3")
    args = parser.parse_args()
    run = ROOT / "artifacts/navigation" / args.run
    showcase = ROOT / "artifacts/showcase" / args.run
    data = np.load(run / "flight.npz")
    log, obstacles = data["log"], data["obstacles"]
    metrics = json.loads((run / "metrics.json").read_text())
    assert metrics["status"] == "success", "navigation did not pass"
    assert np.isfinite(log).all()
    assert np.allclose(np.diff(log[:, 0]), .01, atol=1e-7)
    assert np.max(np.abs(np.linalg.norm(log[:, 7:11], axis=1) - 1)) < 1e-4
    pos = log[:, 1:4]
    radial = np.linalg.norm(pos[:, None, :2] - obstacles[None, :, :2], axis=2) - obstacles[None, :, 2]
    vertical = np.abs(pos[:, None, 2] - obstacles[None, :, 3] / 2) - obstacles[None, :, 3] / 2
    d = np.stack([radial, vertical], axis=-1)
    distances = np.minimum(d.max(axis=-1), 0) + np.linalg.norm(np.maximum(d, 0), axis=-1)
    clear = np.minimum(distances.min(axis=1) - .12, pos[:, 2] - .12)
    assert clear.min() > 0, "collision under conservative envelope"
    path = float(np.linalg.norm(np.diff(pos, axis=0), axis=1).sum())
    assert abs(path - metrics["path_length_m"]) < 1e-6
    last_second = log[log[:, 0] >= log[-1, 0] - .99]
    goal_error = np.linalg.norm(last_second[:, 1:4] - data["goal"], axis=1)
    last_speed = np.linalg.norm(last_second[:, 4:7], axis=1)
    assert goal_error.max() < .5 and last_speed.max() < .2
    assert metrics["render_clock_drift_max_s"] == 0
    assert len(data["depths"]) == metrics["planner_updates"]
    assert len(data["candidates"]) == len(data["scores"]) == len(data["frames"])
    assert data["depths"].shape[1:] == (90, 160)
    assert data["candidates"].shape[1:] == (15, 25, 3)
    csv = np.loadtxt(run / "flight.csv", delimiter=",", skiprows=1)
    assert np.allclose(csv, log)
    video = showcase / "yopo_global_flight.mp4"
    # Isaac's OpenCV build deliberately omits FFmpeg. Use the same standalone
    # imageio-ffmpeg runtime that encoded the video, without replacing OpenCV.
    capture = imageio.get_reader(video, format="ffmpeg")
    fps = capture.get_meta_data()["fps"]
    declared = len(np.arange(0., log[-1, 0] + .0001, .1)) + 40
    count, first, middle, last = 0, None, None, None
    for frame in capture:
        assert frame.shape == (900, 1600, 3)
        if count == 0:
            first = frame.copy()
        if count == declared // 2:
            middle = frame.copy()
        last = frame
        count += 1
    capture.close()
    assert count == declared and count > 100 and abs(fps - 20.) < .01
    difference = float(np.mean(np.abs(first.astype(float) - middle.astype(float))))
    assert difference > .5, "video appears static"
    for name, frame in [("video_first", first), ("video_middle", middle), ("video_last", last)]:
        cv2.imwrite(str(showcase / (name + ".jpg")), frame[:, :, ::-1])
    result = {"validation_passed": True, "run": args.run, "finite_log": True,
              "samples_at_100_hz": len(log), "independent_min_clearance_m": float(clear.min()),
              "path_length_recomputed_m": path, "final_second_max_goal_error_m": float(goal_error.max()),
              "final_second_max_speed_mps": float(last_speed.max()),
              "aligned_depth_and_plan_records": len(data["depths"]),
              "csv_matches_npz": True, "decoded_video_frames": count,
              "video_fps": fps, "video_duration_s": count / fps,
              "video_resolution": [1600, 900], "video_file_bytes": video.stat().st_size,
              "video_sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
              "first_middle_frame_mean_absolute_difference": difference}
    (showcase / "validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
