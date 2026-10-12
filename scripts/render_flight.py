"""Render a global-map replay of measured PhysX states; never reroute the flight."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import traceback
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def draw_plots(data, metrics, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle
    log, obstacles = data["log"], data["obstacles"]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11})
    fig = plt.figure(figsize=(15, 7), facecolor="white")
    grid = fig.add_gridspec(2, 2, width_ratios=[1.7, 1.], hspace=.32, wspace=.24)
    ax = fig.add_subplot(grid[:, 0])
    for x, y, r, _ in obstacles:
        ax.add_patch(Circle((x, y), r, color="#547a6c", alpha=.85))
        ax.add_patch(Circle((x, y), r + .12, fill=False, edgecolor="#a7beb5", linewidth=.7))
    ax.plot(log[:, 1], log[:, 2], color="#da9400", lw=2.5, label="Measured PhysX flight")
    ax.plot([data["start"][0], data["goal"][0]], [data["start"][1], data["goal"][1]], "--", color="#a8b0bb", lw=1, label="Straight start-to-goal line")
    ax.scatter(*data["start"][:2], c="#00a985", s=85, marker="o", zorder=5, label="Start")
    ax.scatter(*data["goal"][:2], c="#168ada", s=130, marker="*", zorder=5, label="Goal")
    ax.set(xlabel="World x [m]", ylabel="World y [m]", xlim=(-2, 26), ylim=(-9, 9), title="Global map · recorded flight trajectory")
    ax.set_aspect("equal")
    ax.grid(alpha=.15)
    ax.legend(loc="lower left", fontsize=9)
    ax2 = fig.add_subplot(grid[0, 1])
    speed = np.linalg.norm(log[:, 4:7], axis=1)
    ax2.plot(log[:, 0], speed, color="#168ada", label="Speed")
    ax2.set(xlabel="Simulation time [s]", ylabel="Speed [m/s]", title="Closed-loop motion")
    ax2.grid(alpha=.18)
    ax3 = fig.add_subplot(grid[1, 1])
    ax3.plot(log[:, 0], log[:, 18], color="#00a985", label="Clearance (0.12 m vehicle envelope)")
    ax3.axhline(0., color="#da5b5b", ls="--", lw=1)
    ax3.set(xlabel="Simulation time [s]", ylabel="Clearance [m]", title=f"Minimum clearance: {metrics['min_clearance_m']:.3f} m")
    ax3.grid(alpha=.18)
    fig.suptitle("YOPO / Isaac Sim — native Windows reproduction", x=.07, ha="left", fontsize=19, fontweight="bold")
    weight_label = metrics.get('weights', 'checkpoint source unspecified')
    fig.text(.07, .025, f"{weight_label} • {metrics['obstacle_count']} obstacles • path {metrics['path_length_m']:.2f} m • goal error {metrics['goal_error_m']:.3f} m • {metrics['status']}", fontsize=10)
    fig.savefig(output / "trajectory_metrics.png", dpi=180, bbox_inches="tight")
    fig.savefig(output / "trajectory_metrics.pdf", bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="forest_seed7_v2")
    parser.add_argument("--preview-only", action="store_true")
    args = parser.parse_args()
    source = ROOT / "artifacts/navigation" / args.run
    output = ROOT / "artifacts/showcase" / args.run
    output.mkdir(parents=True, exist_ok=True)
    data = dict(np.load(source / "flight.npz"))
    metrics = json.loads((source / "metrics.json").read_text())
    draw_plots(data, metrics, output)
    from isaacsim import SimulationApp
    app = SimulationApp({"headless": True, "enable_cameras": True, "width": 1280, "height": 720})
    writer = None
    try:
        import omni.usd
        import omni.replicator.core as rep
        from isaacsim.core.api import World
        from pxr import Gf, UsdGeom, UsdShade, Sdf
        from PIL import Image, ImageDraw, ImageFont
        import imageio.v2 as imageio
        import cv2
        from scene import build_scene

        omni.usd.get_context().new_stage()
        stage = omni.usd.get_context().get_stage()
        build_scene(stage, data["obstacles"], collision=False)
        world = World(stage_units_in_meters=1.)
        # Pure visualization, replaying measured poses; no simulation rerouting.
        vehicle = stage.DefinePrim("/World/Vehicle", "Xform")
        vehicle.GetReferences().AddReference(str(ROOT / "assets/cf21b/cf21B_500_visual.usda"))
        transform = UsdGeom.Xformable(vehicle)
        p_op = transform.AddTranslateOp()
        q_op = transform.AddOrientOp()

        def material(name, color, emissive=0.):
            mat = UsdShade.Material.Define(stage, "/World/Looks/" + name)
            shader = UsdShade.Shader.Define(stage, "/World/Looks/" + name + "/Shader")
            shader.CreateIdAttr("UsdPreviewSurface")
            shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
            shader.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*[v * emissive for v in color]))
            shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(.45)
            mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
            return mat

        trail_mat = material("Gold", (1., .62, .04), 1.0)
        planned_mat = material("Cyan", (.05, .82, 1.), .65)
        lattice_mat = material("Candidate", (.11, .35, .43), .3)
        start_mat = material("Start", (.02, .8, .5), .7)
        goal_mat = material("Goal", (.02, .47, 1.), .8)

        def curve(name, width, mat):
            obj = UsdGeom.BasisCurves.Define(stage, "/World/Lines/" + name)
            obj.CreateTypeAttr("linear")
            obj.CreateWrapAttr("nonperiodic")
            obj.CreateWidthsAttr([width])
            obj.SetWidthsInterpolation("constant")
            UsdShade.MaterialBindingAPI.Apply(obj.GetPrim()).Bind(mat)
            obj.CreatePointsAttr([(0., 0., 0.), (0., 0., 0.)])
            obj.CreateCurveVertexCountsAttr([2])
            return obj

        trail = curve("Flown", .065, trail_mat)
        future = curve("Plan", .04, planned_mat)
        alternatives = curve("Candidates", .012, lattice_mat)
        marker = UsdGeom.Sphere.Define(stage, "/World/VehicleLocator")
        marker.CreateRadiusAttr(.15)
        mark_op = UsdGeom.Xformable(marker).AddTranslateOp()
        UsdShade.MaterialBindingAPI.Apply(marker.GetPrim()).Bind(trail_mat)
        for name, p, mat in [("Start", data["start"], start_mat), ("Goal", data["goal"], goal_mat)]:
            ring = curve(name, .075, mat)
            theta = np.linspace(0, 2 * np.pi, 65)
            points = np.column_stack([p[0] + .6 * np.cos(theta), p[1] + .6 * np.sin(theta), np.full_like(theta, .07)])
            ring.GetPointsAttr().Set(points.tolist())
            ring.GetCurveVertexCountsAttr().Set([len(points)])
            sphere = UsdGeom.Sphere.Define(stage, "/World/" + name + "Mark")
            sphere.CreateRadiusAttr(.18)
            UsdGeom.Xformable(sphere).AddTranslateOp().Set(Gf.Vec3d(*p.tolist()))
            UsdShade.MaterialBindingAPI.Apply(sphere.GetPrim()).Bind(mat)
        camera = rep.create.camera(position=(12., -27., 29.), look_at=(12., 0., 1.2), focal_length=22.)
        product = rep.create.render_product(camera, (1280, 720))
        rgb_ann = rep.AnnotatorRegistry.get_annotator("rgb")
        rgb_ann.attach(product)
        world.reset()
        for _ in range(15):
            rep.orchestrator.step(delta_time=0., rt_subframes=2)
        font_dir = Path("C:/Windows/Fonts")
        title_font = ImageFont.truetype(str(font_dir / "arialbd.ttf"), 32)
        section_font = ImageFont.truetype(str(font_dir / "arialbd.ttf"), 20)
        text_font = ImageFont.truetype(str(font_dir / "arial.ttf"), 18)
        small_font = ImageFont.truetype(str(font_dir / "arial.ttf"), 15)
        log, frames = data["log"], data["frames"]
        replay_times = np.arange(0., log[-1, 0] + .0001, .1)
        if args.preview_only:
            replay_times = np.array([log[-1, 0]])
        else:
            writer = imageio.get_writer(output / "yopo_global_flight.mp4", fps=20, codec="libx264", quality=8,
                                        macro_block_size=2, ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"])

        def minimap(draw, travelled, position):
            bounds = (1310, 158, 1570, 350)
            def xy(p):
                return (bounds[0] + (p[0] + 2) / 28 * (bounds[2] - bounds[0]),
                        bounds[3] - (p[1] + 9) / 18 * (bounds[3] - bounds[1]))
            draw.rectangle(bounds, fill=(20, 32, 42), outline=(55, 72, 85))
            for x, y, radius, _ in data["obstacles"]:
                cx, cy = xy((x, y)); r = radius / 28 * (bounds[2] - bounds[0])
                draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=(80, 118, 104))
            if len(travelled) > 1:
                draw.line([xy(p) for p in travelled], fill=(255, 184, 40), width=2)
            for p, color in [(data["start"], (42, 225, 163)), (data["goal"], (55, 156, 255)), (position, (255, 211, 90))]:
                x, y = xy(p); draw.ellipse((x-4, y-4, x+4, y+4), fill=color)

        for frame_index, t in enumerate(replay_times):
            idx = min(int(np.searchsorted(log[:, 0], t)), len(log) - 1)
            plan_idx = int(np.clip(np.searchsorted(frames[:, 0], t, side="right") - 1, 0, len(frames)-1))
            p, q = log[idx, 1:4], log[idx, 7:11]
            p_op.Set(Gf.Vec3d(*p.tolist()))
            q_op.Set(Gf.Quatf(float(q[0]), Gf.Vec3f(*q[1:].tolist())))
            mark_op.Set(Gf.Vec3d(*p.tolist()))
            travelled = log[:idx+1:5, 1:4]
            if len(travelled) < 2:
                travelled = np.repeat(p[None], 2, axis=0)
            trail.GetPointsAttr().Set(travelled.tolist())
            trail.GetCurveVertexCountsAttr().Set([len(travelled)])
            planned = data["candidates"][plan_idx]
            selected = int(np.argmin(data["scores"][plan_idx]))
            active = t < metrics["arrival_time_s"] if metrics.get("arrival_time_s") is not None else True
            future.GetPointsAttr().Set((planned[selected] if active else np.repeat(p[None], 2, axis=0)).tolist())
            future.GetCurveVertexCountsAttr().Set([len(planned[selected]) if active else 2])
            alternatives.GetPointsAttr().Set((planned.reshape(-1, 3) if active else np.repeat(p[None], 2, axis=0)).tolist())
            alternatives.GetCurveVertexCountsAttr().Set([planned.shape[1]] * len(planned) if active else [2])
            rep.orchestrator.step(delta_time=0., rt_subframes=2)
            image = np.asarray(rgb_ann.get_data())[:, :, :3]
            canvas = Image.new("RGB", (1600, 900), (12, 21, 32))
            canvas.paste(Image.fromarray(image), (0, 88))
            draw = ImageDraw.Draw(canvas)
            draw.text((30, 17), "YOPO  /  ISAAC SIM", font=title_font, fill=(242, 247, 252))
            draw.text((31, 57), "Depth + state to trajectory  |  " + metrics.get('weights', 'checkpoint source unspecified'), font=small_font, fill=(149, 173, 193))
            draw.text((1330, 29), "GLOBAL VIEW", font=section_font, fill=(76, 208, 224))
            draw.text((1310, 113), "TOP-DOWN MAP", font=section_font, fill=(230, 240, 249))
            minimap(draw, travelled, p)
            draw.text((1310, 367), "ONBOARD DEPTH", font=section_font, fill=(230, 240, 249))
            depth = data["depths"][plan_idx].astype(np.float32)
            colored = cv2.applyColorMap(np.uint8(np.clip(depth / 20, 0, 1) * 255), cv2.COLORMAP_TURBO)[:, :, ::-1]
            canvas.paste(Image.fromarray(colored).resize((260, 146)), (1310, 405))
            draw.text((1310, 559), "0 m                         20 m", font=small_font, fill=(144, 166, 183))
            speed = float(np.linalg.norm(log[idx, 4:7]))
            lines = [("SIMULATION TIME", f"{t:05.1f} / {log[-1,0]:.1f} s"),
                     ("SPEED", f"{speed:.2f} m/s"),
                     ("OBSTACLE CLEARANCE", f"{log[idx,18]:.2f} m"),
                     ("GOAL DISTANCE", f"{log[idx,19]:.2f} m")]
            for i, (label, value) in enumerate(lines):
                y = 598 + 49 * i
                draw.text((1310, y), label, font=small_font, fill=(144, 166, 183))
                draw.text((1310, y + 19), value, font=section_font, fill=(242, 247, 252))
            draw.line((0, 809, 1600, 809), fill=(50, 66, 81), width=1)
            draw.text((30, 827), "RECORDED FLIGHT", font=small_font, fill=(255, 190, 60))
            draw.text((225, 827), "SELECTED LOCAL PLAN", font=small_font, fill=(85, 220, 246))
            draw.text((475, 827), "15 CANDIDATES", font=small_font, fill=(124, 158, 169))
            draw.text((710, 827), "2x replay  /  measured PhysX poses", font=small_font, fill=(175, 192, 207))
            draw.text((30, 863), "Map is shown for visualization. The planner receives only onboard depth, state and goal.", font=small_font, fill=(149, 173, 193))
            tag = "GOAL HOLD" if not active else "YOPO NAVIGATION"
            draw.text((1292, 826), tag, font=section_font, fill=(67, 220, 169))
            if writer is not None:
                writer.append_data(np.asarray(canvas))
            if frame_index in (len(replay_times)//2, len(replay_times)-1):
                canvas.save(output / ("global_overview.png" if frame_index == len(replay_times)-1 else "flight_midpoint.png"))
            if frame_index % 80 == 0:
                print(f"RENDER {frame_index + 1}/{len(replay_times)}", flush=True)
        if writer is not None:
            # A short held final frame keeps the complete trajectory visible.
            for _ in range(40):
                writer.append_data(np.asarray(canvas))
            writer.close(); writer = None
        (output / "render_manifest.json").write_text(json.dumps({"source_flight": str(source / "flight.npz"),
             "source_sha256": hashlib.sha256((source / "flight.npz").read_bytes()).hexdigest(),
             "weights": metrics.get('weights'), "weight_sha256": metrics.get('weight_sha256'),
             "video": "yopo_global_flight.mp4", "resolution": [1600,900], "fps": 20,
             "simulation_step_between_frames_s": .1, "playback_speed": 2., "final_hold_frames": 40,
             "replay_of_measured_states": True, "navigation_status": metrics["status"],
             "preview_only": args.preview_only}, indent=2), encoding="utf-8")
        print("RENDER_DONE " + str(output), flush=True)
    except Exception:
        error = traceback.format_exc()
        (output / "render_failure.txt").write_text(error)
        print(error, flush=True)
    finally:
        if writer is not None:
            writer.close()
        app.close()


if __name__ == "__main__":
    main()
