"""YOPO depth-driven navigation with a force-driven Crazyflie in Isaac PhysX.

No map or collision queries are fed to the planner. Map geometry is used only
for rendering, physical contacts and independent evaluation. No pose teleport
is used after the initial reset. Online render steps use delta_time=0.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time
import traceback
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "external/flight_control"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="forest_seed7")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--speed", type=float, default=1.5)
    parser.add_argument("--duration", type=float, default=65.)
    parser.add_argument("--planner", choices=["simple", "main"], default="simple",
                        help="simple = released YOPO-Simple network path (default); main = main-branch network/config used for local training")
    parser.add_argument("--weights", default=None, help="explicit weights file for the chosen planner (default: the released official YOPO-Simple checkpoint)")
    parser.add_argument("--label", default=None, help="provenance label recorded in metrics.json")
    parser.add_argument("--scene", choices=["grid", "forest"], default="grid",
                        help="grid = legacy 20-obstacle lattice scene (default); forest = procedural forest identical to yopo_repro.forest.generate(seed)")
    parser.add_argument("--density", type=float, default=1/30., help="tree density per square metre for --scene forest")
    args = parser.parse_args()
    output = ROOT / "artifacts/navigation" / args.run
    output.mkdir(parents=True, exist_ok=False)
    (output / "status.json").write_text(json.dumps({"status": "running", "config": vars(args)}))
    from isaacsim import SimulationApp
    app = SimulationApp({"headless": True, "enable_cameras": True, "width": 320, "height": 180})
    rows, frames, depths, candidates, scores, plan_times = [], [], [], [], [], []
    try:
        import omni.usd
        import omni.replicator.core as rep
        from isaacsim.core.api import World
        from isaacsim.core.prims import RigidPrim
        from scene import obstacle_map, build_scene, clearance, depth_camera, set_camera_pose
        from cf21b_model import Cf21BParams, body_wrench, rotor_dynamics, rotor_gyroscopic_torque
        from lie_group_adapter import BodyRateLoop, RateLoopConfig, flight_config, make_controller, rotation_from_isaac_quaternion
        if args.planner == "main":
            from yopo_main_adapter import Planner
        else:
            from yopo_adapter import Planner

        if args.scene == "forest":
            from yopo_repro.forest import generate
            obstacles = np.asarray(generate(args.seed, density=args.density)["trees"], dtype=float)
        else:
            obstacles = obstacle_map(args.seed)
        start, goal = np.array([0., 0., 2.]), np.array([23., 0., 2.])
        stage_ctx = omni.usd.get_context()
        stage_ctx.new_stage()
        stage = stage_ctx.get_stage()
        build_scene(stage, obstacles)
        stage.DefinePrim("/World/Drone", "Xform").GetReferences().AddReference(str(ROOT / "assets/cf21b/cf21B_500_physx.usda"))
        physics_dt, control_dt, planning_dt = .002, .01, .1
        world = World(stage_units_in_meters=1., physics_dt=physics_dt, rendering_dt=planning_dt)
        drone = world.scene.add(RigidPrim("/World/Drone", name="quadrotor"))
        camera_ops = depth_camera(stage)
        set_camera_pose(camera_ops, start, np.eye(3))
        product = rep.create.render_product("/World/DepthCamera", (160, 90))
        depth_ann = rep.AnnotatorRegistry.get_annotator("distance_to_image_plane")
        depth_ann.attach(product)
        world.reset()
        drone.set_world_poses(positions=start[None].astype(np.float32), orientations=np.array([[1., 0., 0., 0.]], dtype=np.float32))
        drone.set_linear_velocities(np.zeros((1, 3), np.float32))
        drone.set_angular_velocities(np.zeros((1, 3), np.float32))
        params = Cf21BParams()
        cfg = flight_config()
        cfg.attitude_gain *= .5
        cfg.max_tilt_rad = float(np.deg2rad(28))
        controller = make_controller(cfg)
        inner = BodyRateLoop(params, RateLoopConfig(kp=9., ki=0.))
        rpm = np.full(4, params.hover_rpm)
        if args.planner == "main":
            planner = Planner(start, goal, args.speed, weights=args.weights)
        else:
            planner = Planner(start, goal, args.speed, weights=args.weights)
        # Warm rendering without advancing the physical state.
        for _ in range(12):
            rep.orchestrator.step(delta_time=0., pause_timeline=False, rt_subframes=1)
        initial_clock = float(world.current_time)
        ref = {"position": start.copy(), "velocity": np.zeros(3), "acceleration": np.zeros(3), "yaw": 0.}
        rate_command, thrust_command = np.zeros(3), params.weight
        status = "timeout"
        wall_started = time.perf_counter()
        min_clear, max_render_drift = float("inf"), 0.
        arrival_time = None
        settled_since = None
        for k in range(int(args.duration / physics_dt) + 1):
            t = k * physics_dt
            p_arr, q_arr = drone.get_world_poses()
            p, q = np.asarray(p_arr[0], float), np.asarray(q_arr[0], float)
            v = np.asarray(drone.get_linear_velocities()[0], float)
            rotation = rotation_from_isaac_quaternion(q)
            rates = rotation.T @ np.asarray(drone.get_angular_velocities()[0], float)
            dist_goal = float(np.linalg.norm(goal - p))
            clear = clearance(p, obstacles)
            min_clear = min(min_clear, clear)
            if clear <= 0:
                status = "collision"
                break
            if not np.isfinite(p).all() or np.linalg.norm(p) > 100:
                status = "diverged"
                break
            # Arrival uses 1 m, much stricter than the stock node's 5 m trigger.
            if dist_goal < 1.0 and arrival_time is None:
                arrival_time = t
                # Position hold is a separate terminal mode. Clear flight
                # integrators and use lower-bandwidth horizontal gains so a
                # step to the final goal does not excite the motor/attitude lag.
                hold_cfg = flight_config()
                hold_cfg.attitude_gain *= .5
                hold_cfg.position_gain[:2] = .08
                hold_cfg.velocity_gain[:2] = .12
                hold_cfg.integral_gain[:] = 0.
                controller = make_controller(hold_cfg)
            if arrival_time is not None:
                if dist_goal < .5 and np.linalg.norm(v) < .2:
                    if settled_since is None:
                        settled_since = t
                    if t - settled_since >= 1.0:
                        status = "success"
                        break
                else:
                    settled_since = None
                if t - arrival_time > 20.0:
                    status = "arrival_unsettled"
                    break

            if k % 50 == 0 and arrival_time is None:
                set_camera_pose(camera_ops, p, rotation)
                before = float(world.current_time)
                render_started = time.perf_counter()
                rep.orchestrator.step(delta_time=0., pause_timeline=False, rt_subframes=1)
                depth = np.asarray(depth_ann.get_data(), dtype=np.float32).reshape(90, 160).copy()
                render_ms = (time.perf_counter() - render_started) * 1000
                max_render_drift = max(max_render_drift, abs(float(world.current_time) - before))
                if max_render_drift > physics_dt * .5:
                    raise RuntimeError("Render unexpectedly advanced physics time")
                planner.reference(t, control_dt)
                network_ms = planner.update(depth, rotation, t)
                plan_times.append([t, render_ms, network_ms])
                depths.append(np.clip(np.nan_to_num(depth, nan=20., posinf=20.), 0., 20.).astype(np.float16))
                candidates.append(planner.predictions.copy())
                scores.append(planner.scores.copy())
                frames.append([t, *p, *q, *v, clear, dist_goal, planner.selected_id])
                if k % 2500 == 0:
                    print(f"NAV t={t:.1f}s p={p.round(2).tolist()} goal={dist_goal:.2f} clearance={clear:.2f}", flush=True)
            if k % 5 == 0:
                if arrival_time is None:
                    ref = planner.reference(t + control_dt, control_dt)
                else:
                    ref = {"position": goal, "velocity": np.zeros(3), "acceleration": np.zeros(3), "yaw": planner.yaw}
                ref["max_tilt_rad"] = float(np.deg2rad(28))
                command = controller.compute({"position": p, "velocity": v, "rotation": rotation}, ref, control_dt)
                thrust_command = command["collective_thrust"]
                rate_command = np.asarray(command["body_rate_command"])
                rows.append([t, *p, *v, *q, *ref["position"], *ref["velocity"], thrust_command, clear, dist_goal])
            _, rpm_cmd = inner.step(rate_command, rates, thrust_command, physics_dt)
            rpm_dot = rotor_dynamics(rpm_cmd, rpm, params)
            rpm = np.clip(rpm + physics_dt * rpm_dot, params.rpm_min, params.rpm_max)
            f, torque = body_wrench(rpm, params, rotation.T @ v)
            torque += rotor_gyroscopic_torque(rates, float(np.dot(params.rotor_spin, rpm)), float(np.dot(params.rotor_spin, rpm_dot)), params)
            drone.apply_forces_and_torques_at_pos((rotation @ f)[None].astype(np.float32), (rotation @ torque)[None].astype(np.float32), is_global=True)
            world.step(render=False)

        elapsed = time.perf_counter() - wall_started
        log = np.asarray(rows)
        path_length = float(np.linalg.norm(np.diff(log[:, 1:4], axis=0), axis=1).sum())
        speeds = np.linalg.norm(log[:, 4:7], axis=1)
        tracking = np.linalg.norm(log[:, 1:4] - log[:, 11:14], axis=1)
        timings = np.asarray(plan_times)
        weight = Path(args.weights) if args.weights else ROOT / "external/audit_sources/YOPO-Simple/YOPO/saved/YOPO_1/epoch50.pth"
        weight = weight if weight.is_absolute() else ROOT / weight
        metrics = {"status": status, "seed": args.seed, "source_commit": "bd8a7f91953cfef9f1aa9a48d7ff0ab7bceee132",
                   "weight_sha256": hashlib.sha256(weight.read_bytes()).hexdigest(),
                   "weights": args.label or ("official pretrained epoch50; not retrained" if not args.weights else str(weight)),
                   "weights_path": str(weight.relative_to(ROOT).as_posix() if weight.is_relative_to(ROOT) else weight),
                   "planner": "YOPO depth/state only, argmin score; reference-state replanning", "planner_network": args.planner,
                   "physics": "Isaac Sim 6.1 PhysX rigid body + rotor dynamics + geometric outer/inner control",
                   "start": start.tolist(), "goal": goal.tolist(), "final_position": p.tolist(), "goal_error_m": dist_goal,
                   "final_speed_mps": float(np.linalg.norm(v)),
                   "success_criteria": "goal error <0.5m and speed <0.2m/s continuously for 1s, no collision",
                   "terminal_hold": "within 1m: reset integrators, position hold with horizontal Kp=.08 and Kv=.12; no map input",
                   "sim_duration_s": t, "arrival_time_s": arrival_time, "wall_runtime_s": elapsed,
                   "real_time_factor": t / elapsed, "path_length_m": path_length, "max_speed_mps": float(speeds.max()),
                   "mean_speed_mps": float(speeds.mean()), "min_clearance_m": min_clear,
                   "collision_eval_radius_m": .12, "tracking_rmse_m": float(np.sqrt(np.mean(tracking ** 2))),
                   "planner_updates": len(plan_times), "planning_hz_sim": 10., "physics_hz": 500., "control_hz": 100.,
                   "render_clock_drift_max_s": max_render_drift,
                   "final_clock_difference_s": float(world.current_time) - initial_clock - t,
                   "network_pipeline_p50_ms": float(np.percentile(timings[:, 2], 50)),
                   "network_pipeline_p95_ms": float(np.percentile(timings[:, 2], 95)),
                   "depth_render_readback_p50_ms": float(np.percentile(timings[:, 1], 50)),
                   "depth_render_readback_p95_ms": float(np.percentile(timings[:, 1], 95)),
                   "obstacle_count": len(obstacles), "map_used_for_planning": False}
        metrics["scene_model"] = args.scene
        metrics["scene_density_per_m2"] = float(args.density) if args.scene == "forest" else None
        np.savez_compressed(output / "flight.npz", log=log, frames=np.asarray(frames), depths=np.asarray(depths),
                            candidates=np.asarray(candidates), scores=np.asarray(scores), plan_times=timings,
                            obstacles=obstacles, start=start, goal=goal)
        np.savetxt(output / "flight.csv", log, delimiter=",", header="t,x,y,z,vx,vy,vz,qw,qx,qy,qz,rx,ry,rz,rvx,rvy,rvz,thrust,clearance,goal_error", comments="")
        (output / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        (output / "status.json").write_text(json.dumps({"status": status}), encoding="utf-8")
        print("NAV_RESULT " + json.dumps(metrics), flush=True)
    except Exception:
        failure = traceback.format_exc()
        (output / "failure.txt").write_text(failure)
        (output / "status.json").write_text(json.dumps({"status": "error"}))
        print(failure, flush=True)
    finally:
        app.close()


if __name__ == "__main__":
    main()
