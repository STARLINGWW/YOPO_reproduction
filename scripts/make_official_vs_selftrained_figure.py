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

# (scene, speed, panel caption)
PANELS = [
    (5001, 2, "场景 5001 · 2 m/s（困难）"),
    (5004, 4, "场景 5004 · 4 m/s（中等）"),
    (5002, 6, "场景 5002 · 6 m/s（简单）"),
]

GIF_SCENE = 5001
GIF_SPEED = 2
GIF_WINDOW_S = 20.0
GIF_FPS = 10


def load_pair(scene, speed):
    runs = {}
    for label, prefix in (("official", OFFICIAL_RUN), ("local", LOCAL_RUN)):
        folder = NAV / f"{prefix}_s{scene}_v{speed}"
        data = dict(np.load(folder / "flight.npz"))
        metrics = json.loads((folder / "metrics.json").read_text(encoding="utf-8"))
        runs[label] = {"folder": folder.name, "log": data["log"], "obstacles": data["obstacles"],
                       "start": data["start"], "goal": data["goal"], "metrics": metrics}
    return runs


STATUS_ZH = {"success": "到达", "timeout": "超时", "collision": "碰撞", "crashed": "崩溃", "out_of_map": "越界"}


def outcome_text(m):
    status = STATUS_ZH.get(m.get("status"), str(m.get("status")))
    if m.get("status") == "success":
        return f"{status} {m['arrival_time_s']:.1f} s · RMSE {m.get('tracking_rmse_m', float('nan')):.2f} m"
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
                    label=f"{label}（{outcome_text(run['metrics'])}）")
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
             "来源：weights A/B 36 架次受控对照（独立 scope，不进入冻结矩阵）。左：自训练胜（官方超时）；中：官方胜（自训练超时）；右：均到达，官方更快、自训练跟踪更稳。",
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
    o_log, l_log = runs["official"]["log"], runs["local"]["log"]

    def sample(log, t):
        idx = np.searchsorted(log[:, 0], t, side="right") - 1
        idx = max(0, min(idx, len(log) - 1))
        return log[idx]

    fig, axes = plt.subplots(1, 2, figsize=(9.8, 4.4), facecolor="white")
    fig.subplots_adjust(left=.06, right=.99, top=.86, bottom=.11, wspace=.16)
    artists = []
    for ax, (run, color, name) in zip(axes, ((runs["official"], C_OFFICIAL, "官方 epoch50"),
                                             (runs["local"], C_LOCAL, "自训练 seed0"))):
        draw_map(ax, run)
        ax.set_xlim(-3, 27); ax.set_ylim(-9.5, 9.5); ax.set_aspect("equal"); ax.grid(alpha=.15)
        ax.set_xlabel("World x [m]", fontsize=9); ax.set_ylabel("World y [m]", fontsize=9)
        ax.set_title(f"{name} — {STATUS_ZH.get(run['metrics'].get('status'))}", fontsize=12, fontweight="bold", color=color)
        trail, = ax.plot([], [], color=color, lw=2.0)
        dot, = ax.plot([], [], marker="o", color=color, ms=7, mec="white", mew=1.0)
        readout = ax.text(.99, .035, "", transform=ax.transAxes, ha="right", va="bottom", fontsize=9,
                          bbox=dict(boxstyle="round,pad=.32", fc="white", ec="#b9c2cd", alpha=.95))
        artists.append({"ax": ax, "run": run, "trail": trail, "dot": dot, "readout": readout, "log": run["log"]})
    fig.suptitle("同场景动态对照（场景 5001 · 2 m/s · 共同时间窗 0–20 s）：官方（左）| 自训练（右）",
                 fontsize=12.5, fontweight="bold")
    frames = []
    total = int(GIF_WINDOW_S * GIF_FPS)
    for k in range(total + int(2.0 * GIF_FPS)):
        t = min(GIF_WINDOW_S, k / GIF_FPS)
        for a in artists:
            row = sample(a["log"], t)
            n = int(np.searchsorted(a["log"][:, 0], t, side="right"))
            n = max(1, n)
            a["trail"].set_data(a["log"][:n, 1], a["log"][:n, 2])
            a["dot"].set_data([row[1]], [row[2]])
            speed = float(np.linalg.norm(row[4:7]))
            a["readout"].set_text(f"t={t:4.1f}s  速度 {speed:4.1f} m/s  距终点 {row[19]:4.1f} m")
        if k >= total:
            for a, final in zip(artists, (
                    "官方：20 s 窗口结束仍在搜索（120 s 上限 → 超时）",
                    f"自训练：{runs['local']['metrics']['arrival_time_s']:.1f} s 到达终点")):
                a["readout"].set_text(final)
        fig.canvas.draw()
        buf = np.asarray(fig.canvas.buffer_rgba())[:, :, :3]
        frames.append(buf.copy())
    plt.close(fig)
    out = MEDIA / "02_same_scene_compare.gif"
    imageio.mimsave(out, frames, fps=GIF_FPS, loop=0)
    size_mb = out.stat().st_size / 1024 / 1024
    print(f"wrote {out.relative_to(ROOT).as_posix()} ({size_mb:.1f} MB, {len(frames)} frames)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-gif", action="store_true")
    args = parser.parse_args()
    render_static()
    if not args.skip_gif:
        render_gif()


if __name__ == "__main__":
    main()
