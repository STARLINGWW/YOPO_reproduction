"""Render the official-vs-self-trained comparison assets used by the README.

Reads the matched same-scene closed-loop pairs from the weights A/B campaign
(`artifacts/navigation/wab2_main_*`, 3 scenes x 3 speeds x 4 arms, outside the
frozen matrix; the raw runs live in the external archive). Produces:

  media/official_vs_selftrained/01_same_scene_trajectories.png
      three representative same-scene pairs (main stack): one where the
      self-trained policy wins, one where the official weights win, and one
      where both arrive with different speed/tracking trade-offs;

  media/official_vs_selftrained/02_same_scene_compare.gif
      synchronized side-by-side replay (official | self-trained) of scene 5001
      at 2 m/s inside a common 0-20 s window.

Outputs are committed assets; the raw flight logs need the external archive
(see report/06_migration). Rendering only reads recorded logs, it never
reroutes a flight.
"""
from pathlib import Path
import argparse
import json
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "report/05_visualization/media/official_vs_selftrained"
NAV = ROOT / "artifacts/navigation"

OFFICIAL_RUN = "wab2_main_official"
LOCAL_RUN = "wab2_main_local"

C_OFFICIAL = "#da9400"
C_LOCAL = "#168ada"
C_OBSTACLE = "#547a6c"
C_OBSTACLE_EDGE = "#a7beb5"

# Matched same-scene pairs where BOTH policies finish (main stack).
PANELS = [
    (5001, 4, "场景 5001 · 4 m/s（困难）"),
    (5004, 2, "场景 5004 · 2 m/s（中等）"),
    (5002, 6, "场景 5002 · 6 m/s（简单）"),
]

GIF_SCENE = 5001
GIF_SPEED = 4
GIF_FPS = 10

DEPTH_SCENE = 5001
DEPTH_SPEED = 4
DEPTH_TIMES = (0.5, 2.0, 4.0)


def load_pair(scene, speed):
    runs = {}
    for label, prefix in (("official", OFFICIAL_RUN), ("local", LOCAL_RUN)):
        folder = NAV / f"{prefix}_s{scene}_v{speed}"
        data = dict(np.load(folder / "flight.npz"))
        metrics = json.loads((folder / "metrics.json").read_text(encoding="utf-8"))
        runs[label] = {"folder": folder.name, "log": data["log"], "obstacles": data["obstacles"],
                       "start": data["start"], "goal": data["goal"], "metrics": metrics,
                       "frames": data["frames"], "depths": data["depths"]}
    return runs


STATUS_ZH = {"success": "到达", "timeout": "超时", "collision": "碰撞", "crashed": "崩溃", "out_of_map": "越界"}


def settled_time(run):
    """Legacy-harness success moment: goal error < 0.5 m and speed < 0.2 m/s held for 1 s."""
    log, goal = run["log"], run["goal"][:2]
    t = log[:, 0]
    dist = np.linalg.norm(log[:, 1:3] - goal, axis=1)
    speed = np.linalg.norm(log[:, 4:7], axis=1)
    ok = (dist < .5) & (speed < .2)
    for i in range(len(t)):
        if ok[i:].all() and (t[-1] - t[i]) >= .9:
            return float(t[-1])
    return None


def outcome_text(run):
    m = run["metrics"]
    status = STATUS_ZH.get(m.get("status"), str(m.get("status")))
    if m.get("status") == "success":
        settled = settled_time(run)
        return (f"入圈 {m['arrival_time_s']:.1f} s → 稳定达标 {settled:.1f} s · "
                f"RMSE {m.get('tracking_rmse_m', float('nan')):.2f} m")
    return f"{status} · 路径 {m.get('path_length_m', float('nan')):.0f} m · RMSE {m.get('tracking_rmse_m', float('nan')):.2f} m"


def set_cjk_font(plt):
    from matplotlib import font_manager
    for candidate in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/simhei.ttf"):
        if Path(candidate).is_file():
            prop = font_manager.FontProperties(fname=candidate)
            plt.rcParams["font.family"] = prop.get_name()
            font_manager.fontManager.addfont(candidate)
            plt.rcParams["font.family"] = prop.get_name()
            return True
    return False


def draw_map(ax, run, lw=2.2, alpha=1.0, trail_end=None):
    log = run["log"]
    end = len(log) if trail_end is None else min(len(log), trail_end)
    for x, y, r, _ in run["obstacles"]:
        from matplotlib.patches import Circle
        ax.add_patch(Circle((x, y), r, color=C_OBSTACLE, alpha=.85, zorder=1))
        ax.add_patch(Circle((x, y), r + .12, fill=False, edgecolor=C_OBSTACLE_EDGE, linewidth=.7, zorder=1))
    ax.plot([run["start"][0], run["goal"][0]], [run["start"][1], run["goal"][1]], "--",
            color="#c3cad4", lw=1.0, zorder=2)
    ax.scatter(*run["start"][:2], c="#00a985", s=70, marker="o", zorder=6)
    ax.scatter(*run["goal"][:2], c="#168ada", s=150, marker="*", zorder=6)


def render_static():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    set_cjk_font(plt)
    fig, axes = plt.subplots(1, 3, figsize=(13.8, 4.9), facecolor="white")
    for ax, (scene, speed, caption) in zip(axes, PANELS):
        runs = load_pair(scene, speed)
        for run, color, label in ((runs["official"], C_OFFICIAL, "官方 epoch50"),
                                  (runs["local"], C_LOCAL, "自训练 seed0")):
            draw_map(ax, run)
            log = run["log"]
            ax.plot(log[:, 1], log[:, 2], color=color, lw=2.2, alpha=.95,
                    label=f"{label}（{outcome_text(run)}）")
            ax.plot(log[0, 1], log[0, 2], marker="o", color=color, ms=5, zorder=7)
        ax.set_title(caption, fontsize=12.5, fontweight="bold")
        ax.set_xlim(-3, 27)
        ax.set_ylim(-9.5, 9.5)
        ax.set_aspect("equal")
        ax.grid(alpha=.15)
        ax.set_xlabel("World x [m]", fontsize=10)
        ax.set_ylabel("World y [m]", fontsize=10)
        ax.legend(loc="lower left", fontsize=8.2, framealpha=.92)
    fig.suptitle("官方预训练 vs 自训练：同场景（同地图/同起点终点/同速度）闭环轨迹直接对照（main 栈）",
                 fontsize=14.5, fontweight="bold", y=.995)
    fig.text(.005, .012,
             "判据：终点误差 <0.5 m 且速度 <0.2 m/s 连续 1 s（无碰撞）。「入圈」= 首次进入终点 1 m 半径（终端低速保持切换点）；"
             "终点附近的折返是高速过冲后的回稳。全量 36 架次与冻结矩阵口径见 report/04_evaluation/01_official_vs_selftrained.md。",
             fontsize=9, color="#444444")
    fig.tight_layout(rect=(0, .035, 1, .97))
    MEDIA.mkdir(parents=True, exist_ok=True)
    out = MEDIA / "01_same_scene_trajectories.png"
    fig.savefig(out, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", out.relative_to(ROOT).as_posix())


def render_gif():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import imageio.v2 as imageio
    set_cjk_font(plt)
    runs = load_pair(GIF_SCENE, GIF_SPEED)

    def sample(log, t):
        idx = np.searchsorted(log[:, 0], t, side="right") - 1
        idx = max(0, min(idx, len(log) - 1))
        return log[idx]

    def depth_idx(run, t):
        times = run["frames"][:, 0]
        return int(np.argmin(np.abs(times - t)))

    gif_window = float(max(runs["official"]["metrics"]["arrival_time_s"],
                           runs["local"]["metrics"]["arrival_time_s"]) + 2.5)
    fig = plt.figure(figsize=(9.8, 6.4), facecolor="white")
    grid = fig.add_gridspec(2, 2, height_ratios=[1.30, 1.0], hspace=.30, wspace=.16,
                            left=.055, right=.905, top=.88, bottom=.06)
    artists = []
    ims = []
    for col, (run, color, name) in enumerate(((runs["official"], C_OFFICIAL, "官方 epoch50"),
                                              (runs["local"], C_LOCAL, "自训练 seed0"))):
        ax = fig.add_subplot(grid[0, col])
        draw_map(ax, run)
        ax.set_xlim(-3, 27); ax.set_ylim(-9.5, 9.5); ax.set_aspect("equal"); ax.grid(alpha=.15)
        ax.set_xlabel("World x [m]", fontsize=9); ax.set_ylabel("World y [m]", fontsize=9)
        ax.set_title(f"{name} — {STATUS_ZH.get(run['metrics'].get('status'))}", fontsize=12, fontweight="bold", color=color)
        trail, = ax.plot([], [], color=color, lw=2.0)
        dot, = ax.plot([], [], marker="o", color=color, ms=7, mec="white", mew=1.0)
        readout = ax.text(.99, .035, "", transform=ax.transAxes, ha="right", va="bottom", fontsize=9,
                          bbox=dict(boxstyle="round,pad=.32", fc="white", ec="#b9c2cd", alpha=.95))
        dax = fig.add_subplot(grid[1, col])
        im = dax.imshow(run["depths"][0].astype("float32"), cmap="turbo", vmin=0.0, vmax=20.0, interpolation="nearest")
        dax.set_xticks([]); dax.set_yticks([])
        dtitle = dax.set_title("机载深度 t=0.0 s", fontsize=10.5, color=color)
        badge = dax.text(.5, .52, "", transform=dax.transAxes, ha="center", va="center", fontsize=12,
                         fontweight="bold", color="white", visible=False,
                         bbox=dict(boxstyle="round,pad=.45", fc="#1f2a37", ec="white", alpha=.88))
        ims.append(im)
        artists.append({"run": run, "trail": trail, "dot": dot, "readout": readout,
                        "im": im, "dtitle": dtitle, "badge": badge, "log": run["log"],
                        "depth_times": run["frames"][:, 0]})
    cax = fig.add_axes([.915, .10, .016, .25])
    cbar = fig.colorbar(ims[0], cax=cax)
    cbar.set_label("深度 [m]", fontsize=9)
    fig.suptitle(f"同场景动态对照（场景 {GIF_SCENE} · {GIF_SPEED} m/s · 共同时间窗 0–{gif_window:.1f} s）：轨迹（上）与机载深度（下）；官方（左）| 自训练（右）",
                 fontsize=11.5, fontweight="bold", y=.98)
    frames = []
    total = int(gif_window * GIF_FPS)
    for k in range(total + int(2.0 * GIF_FPS)):
        t = min(gif_window, k / GIF_FPS)
        for a in artists:
            row = sample(a["log"], t)
            n = int(np.searchsorted(a["log"][:, 0], t, side="right"))
            n = max(1, n)
            a["trail"].set_data(a["log"][:n, 1], a["log"][:n, 2])
            a["dot"].set_data([row[1]], [row[2]])
            speed = float(np.linalg.norm(row[4:7]))
            a["readout"].set_text(f"t={t:4.1f}s  速度 {speed:4.1f} m/s  距终点 {row[19]:4.1f} m")
            di = depth_idx(a["run"], t)
            a["im"].set_data(a["run"]["depths"][di].astype("float32"))
            depth_end = float(a["depth_times"][di])
            capture_over = t > float(a["depth_times"][-1]) + 1e-6
            if capture_over:
                a["im"].set_alpha(.35)
                a["badge"].set_text(f"已到达 · 深度采集结束（t={a['depth_times'][-1]:.1f} s）")
                a["badge"].set_visible(True)
                a["dtitle"].set_text(f"机载深度（采集至 {a['depth_times'][-1]:.1f} s）")
            else:
                a["im"].set_alpha(1.0)
                a["badge"].set_visible(False)
                a["dtitle"].set_text(f"机载深度 t={depth_end:.1f} s")
        if k >= total:
            for a, final in zip(artists, (
                    f"官方：{runs['official']['metrics']['arrival_time_s']:.1f} s 入 1 m 圈 → {settled_time(runs['official']):.1f} s 稳定达标",
                    f"自训练：{runs['local']['metrics']['arrival_time_s']:.1f} s 入 1 m 圈 → {settled_time(runs['local']):.1f} s 稳定达标")):
                a["readout"].set_text(final)
        fig.canvas.draw()
        buf = np.asarray(fig.canvas.buffer_rgba())[:, :, :3]
        frames.append(buf.copy())
    plt.close(fig)
    out = MEDIA / "02_same_scene_compare.gif"
    imageio.mimsave(out, frames, fps=GIF_FPS, loop=0)
    size_mb = out.stat().st_size / 1024 / 1024
    print(f"wrote {out.relative_to(ROOT).as_posix()} ({size_mb:.1f} MB, {len(frames)} frames)")


def nearest_frame_idx(frames, t):
    return int(np.argmin(np.abs(frames[:, 0] - t)))


def render_depth():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    set_cjk_font(plt)
    o = dict(np.load(NAV / f"{OFFICIAL_RUN}_s{DEPTH_SCENE}_v{DEPTH_SPEED}" / "flight.npz"))
    l = dict(np.load(NAV / f"{LOCAL_RUN}_s{DEPTH_SCENE}_v{DEPTH_SPEED}" / "flight.npz"))
    fig, axes = plt.subplots(2, len(DEPTH_TIMES), figsize=(10.8, 4.9), facecolor="white")
    im = None
    for row, (data, name, color) in enumerate(((o, "官方 epoch50", C_OFFICIAL), (l, "自训练 seed0", C_LOCAL))):
        for col, t in enumerate(DEPTH_TIMES):
            ax = axes[row][col]
            frames = data["frames"]
            idx = nearest_frame_idx(frames, t)
            depth = data["depths"][idx].astype("float32")
            im = ax.imshow(depth, cmap="turbo", vmin=0.0, vmax=20.0, interpolation="nearest")
            ax.set_xticks([]); ax.set_yticks([])
            if row == 0:
                ax.set_title(f"t = {frames[idx,0]:.1f} s", fontsize=11, fontweight="bold")
            if col == 0:
                ax.set_ylabel(name, fontsize=11, color=color, fontweight="bold")
    fig.suptitle("机载深度相机渲染（场景 5001 · 4 m/s，双方都到达；网络输入为 min(depth,20)/20 的 160×96）",
                 fontsize=12.5, fontweight="bold", y=.99)
    fig.subplots_adjust(left=.12, right=.90, top=.86, bottom=.06, wspace=.05, hspace=.08)
    cax = fig.add_axes([.915, .15, .018, .62])
    cbar = fig.colorbar(im, cax=cax)
    cbar.set_label("深度 [m]", fontsize=10)
    out = MEDIA / "03_depth_frames.png"
    fig.savefig(out, dpi=175, facecolor="white")
    plt.close(fig)
    print("wrote", out.relative_to(ROOT).as_posix())


def render_terminal():
    """Annotate the terminal phase (1 m gate -> overshoot -> sustained settle)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    set_cjk_font(plt)
    runs = load_pair(5001, 4)
    fig, axes = plt.subplots(1, 2, figsize=(12.6, 4.6), facecolor="white",
                             gridspec_kw=dict(width_ratios=[1.25, 1.0]))
    ax, ax2 = axes
    for run, color, name in ((runs["official"], C_OFFICIAL, "官方 epoch50"),
                             (runs["local"], C_LOCAL, "自训练 seed0")):
        log, goal = run["log"], run["goal"][:2]
        t = log[:, 0]
        pos = log[:, 1:3]
        speed = np.linalg.norm(log[:, 4:7], axis=1)
        dist = np.linalg.norm(pos - goal, axis=1)
        gate = run["metrics"]["arrival_time_s"]
        i_gate = int(np.searchsorted(t, gate))
        i_far = int(np.argmax(dist[i_gate:])) + i_gate
        settled = settled_time(run) or float(t[-1])
        ax.plot(pos[:, 0], pos[:, 1], color=color, lw=2.2, label=name)
        ax.scatter(*pos[i_gate], color=color, s=70, marker="o", ec="white", zorder=6)
        ax.annotate(f"{name} 入圈 {gate:.1f} s\n(速度 {speed[i_gate]:.1f} m/s)",
                    xy=pos[i_gate], xytext=(pos[i_gate, 0] - 6.5, pos[i_gate, 1] + 2.2),
                    fontsize=9, color=color, arrowprops=dict(arrowstyle="->", color=color, lw=1))
        ax.scatter(*pos[i_far], color=color, s=70, marker="x", zorder=6)
        ax.annotate(f"最远 {dist[i_far]:.2f} m (t={t[i_far]:.1f} s)",
                    xy=pos[i_far], xytext=(pos[i_far, 0] + .4, pos[i_far, 1] + 1.6),
                    fontsize=9, color=color, arrowprops=dict(arrowstyle="->", color=color, lw=1))
        ax2.plot(t, dist, color=color, lw=2.0, label=f"{name} 距终点")
        ax2.axvline(gate, color=color, ls=":", lw=1.2, alpha=.8)
        ax2.axvline(settled, color=color, ls="--", lw=1.2, alpha=.8)
    goal = runs["official"]["goal"][:2]
    ax.scatter(*goal, c="#168ada", s=150, marker="*", zorder=7)
    ax.annotate("终点", xy=goal, xytext=(goal[0] + .3, goal[1] - 1.8), fontsize=10, color="#168ada")
    ax.add_patch(plt.Circle(goal, 1.0, fill=False, ec="#9aa4b1", ls="--", lw=1.2))
    ax.add_patch(plt.Circle(goal, 0.5, fill=False, ec="#c3cad4", ls=":", lw=1.2))
    ax.set(xlim=(18, 27), ylim=(-4.5, 4.5), xlabel="World x [m]", ylabel="World y [m]",
           title="终点阶段放大：1 m 止盈圈（虚线）与 0.5 m 判据圈（点线）")
    ax.set_aspect("equal"); ax.grid(alpha=.15); ax.legend(loc="lower left", fontsize=8.6)
    ax2.set(xlabel="仿真时间 [s]", ylabel="距终点 [m]",
            title="距终点随时间：入圈（点线）→ 过冲 → 稳定达标（虚线）")
    ax2.axhline(1.0, color="#9aa4b1", lw=1, ls="--")
    ax2.axhline(0.5, color="#c3cad4", lw=1, ls=":")
    ax2.axvline(runs["official"]["metrics"]["arrival_time_s"], color=C_OFFICIAL, ls=":", lw=1.2, alpha=.8)
    ax2.axvline(runs["local"]["metrics"]["arrival_time_s"], color=C_LOCAL, ls=":", lw=1.2, alpha=.8)
    ax2.axvline(settled_time(runs["official"]) or 0, color=C_OFFICIAL, ls="--", lw=1.2, alpha=.8)
    ax2.axvline(settled_time(runs["local"]) or 0, color=C_LOCAL, ls="--", lw=1.2, alpha=.8)
    ax2.grid(alpha=.15); ax2.legend(loc="upper right", fontsize=8.6)
    fig.suptitle("同一场景（5001 · 4 m/s）：折返 = 入圈后高速余量的过冲回稳（非绕行、非判据差异）",
                 fontsize=13, fontweight="bold", y=.99)
    fig.tight_layout(rect=(0, 0, 1, .94))
    out = MEDIA / "04_terminal_phase.png"
    fig.savefig(out, dpi=170, facecolor="white")
    plt.close(fig)
    print("wrote", out.relative_to(ROOT).as_posix())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-gif", action="store_true")
    args = parser.parse_args()
    render_static()
    if not args.skip_gif:
        render_gif()
    render_depth()
    render_terminal()


if __name__ == "__main__":
    main()
