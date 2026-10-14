"""Render paper-style success / collision vs forward-speed figures (Fig.7 layout).

Two frozen, read-only evidence sources:
  * artifacts/benchmark_summary/summary.json      - active 1,500-slot ROS2 matrix
                                                    (subset "all30"; YOPO seeds pooled)
  * artifacts/weights_ab_demo/batch_summary.json  - native official-vs-self-trained A/B
                                                    (main stack, sparse + dense, 2-10 m/s)

Matrix figures (Fig.7 layout, one panel per density: sparse 1/30, dense 1/20):
  report/00_index/media/success_vs_speed.png
  report/00_index/media/collision_vs_speed.png
A/B figure (2x2: rows success/collision, columns sparse/dense; main stack only):
  report/00_index/media/official_vs_selftrained_vs_speed.png

The official weights cannot run in the frozen ROS2 matrix (source-provenance gate),
so they are only drawn in the dedicated native A/B figure, never mixed into the
matrix panels. The script also prints the underlying numbers as Markdown tables.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "artifacts/benchmark_summary/summary.json"
AB_BATCH = ROOT / "artifacts/weights_ab_demo/batch_summary.json"
MEDIA = ROOT / "report/00_index/media"

SPEEDS = [2, 4, 6, 8, 10]
CONDITIONS = {"sparse": "sparse  (\u03c1 = 1/30 m$^{-2}$)", "dense": "dense  (\u03c1 = 1/20 m$^{-2}$)"}
MODELS = {
    "yopo": ("Proposed: self-trained YOPO (n=90/point)", "#b2182b", "-", "o"),
    "official": ("Official YOPO weights, native A/B chain (n=5/point)", "#2166ac", "--", "s"),
    "topotraj": ("TopoTraj (n=30/point)", "#1b9e77", "-", "^"),
    "agile": ("Agile Autonomy (n=30/point)", "#e08214", "-", "D"),
}


def matrix_rates():
    """(condition, speed) -> per-model (success, collision, timeout, n) from the frozen matrix."""
    data = json.loads(SUMMARY.read_text(encoding="utf-8"))
    rates = {}
    for group in data["groups"]:
        if group.get("subset") != "all30":
            continue
        condition = group["condition"]
        speed = int(group["speed_mps"])
        outcomes = group["outcomes"]
        rates[(condition, speed, group["model"])] = (
            outcomes.get("success", 0), outcomes.get("collision", 0),
            outcomes.get("timeout", 0), group["completed"],
        )
    return rates


def ab_rates():
    """(condition, arm, speed) -> (success, collision, timeout, n) from the native A/B batch."""
    data = json.loads(AB_BATCH.read_text(encoding="utf-8"))
    rates = {}
    maps = {}
    for record in data["records"]:
        if not record["arm"].startswith("main_"):
            continue
        density = record.get("scene_density_per_m2")
        if density is None:
            continue
        condition = "sparse" if density < 0.04 else "dense"
        maps.setdefault(condition, set()).add(int(record["seed"]))
        key = (condition, record["arm"], int(record["speed_mps"]))
        bucket = rates.setdefault(key, {"success": 0, "collision": 0, "timeout": 0, "n": 0})
        bucket["success"] += record["status"] == "success"
        bucket["collision"] += record["status"] == "collision"
        bucket["timeout"] += record["status"] == "timeout"
        bucket["n"] += 1
    maps = {condition: sorted(seeds) for condition, seeds in maps.items()}
    return rates, maps


def render_ab(rates, maps, path):
    """2x2 paper-style grid: rows = success/collision, columns = sparse/dense (native A/B)."""
    arms = {
        "main_local": ("Self-trained seed0 (main stack, n=5/point)", "#b2182b", "-", "o"),
        "main_official": ("Official epoch50 (main layout, n=5/point)", "#2166ac", "--", "s"),
    }
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif"],
        "axes.linewidth": 1.0,
    })
    fig, axes = plt.subplots(2, 2, figsize=(10.6, 7.2), dpi=200, sharex=True)
    for row, metric in enumerate(("success", "collision")):
        for col, condition in enumerate(("sparse", "dense")):
            ax = axes[row][col]
            for arm, (name, colour, style, marker) in arms.items():
                pts = sorted((v, rates[(condition, arm, v)]) for v in SPEEDS if (condition, arm, v) in rates)
                if not pts:
                    continue
                xs = [p[0] for p in pts]
                ys = [100.0 * p[1][metric] / p[1]["n"] for p in pts]
                ax.plot(xs, ys, style, color=colour, marker=marker, markersize=6,
                        markerfacecolor="white" if arm == "main_official" else colour,
                        markeredgewidth=1.3, linewidth=1.9, label=name)
            ax.set_xlim(1.4, 10.6)
            ax.set_ylim(-2, 102)
            ax.set_xticks(SPEEDS)
            ax.set_yticks([0, 20, 40, 60, 80, 100])
            ax.grid(True, color="#d9d9d9", linewidth=0.8)
            ax.set_axisbelow(True)
            ax.tick_params(labelsize=9.5)
            if col == 0:
                ax.set_ylabel(("Success Rate [%]" if metric == "success" else "Collision Rate [%]"), fontsize=10.5)
            if row == 1:
                ax.set_xlabel("Forward Speed [m/s]", fontsize=10.5)
            if row == 0 and col == 1:
                ax.legend(loc="upper right", fontsize=8.2, framealpha=0.92)
    fig.text(0.30, 0.945, "(a) sparse scenario", ha="center", fontsize=11)
    fig.text(0.78, 0.945, "(b) dense scenario", ha="center", fontsize=11)
    fig.text(0.5, 0.015,
             "Native A/B chain (outside the frozen ROS2 matrix): one flight per map, "
             f"n = {len(maps.get('sparse', []))} per point "
             f"(sparse {','.join(str(s) for s in maps.get('sparse', []))}; "
             f"dense {','.join(str(s) for s in maps.get('dense', []))}; 120 s sim cap)",
             ha="center", fontsize=7.6, color="#666666")
    fig.tight_layout(rect=(0, 0.045, 1, 0.925))
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    print("wrote", path.relative_to(ROOT).as_posix())


def series(rates, ab, kind):
    """Build {condition: {model: [(speed, rate, n)]}} for 'success' or 'collision'."""
    out = {}
    for condition in CONDITIONS:
        curves = {}
        pooled = []
        for speed in SPEEDS:
            s = c = t = n = 0
            for seed in range(3):
                if (condition, speed, f"yopo_seed{seed}") in rates:
                    a, b, d, m = rates[(condition, speed, f"yopo_seed{seed}")]
                    s, c, t, n = s + a, c + b, t + d, n + m
            pooled.append((speed, 100.0 * (s if kind == "success" else c) / n, n, c))
        curves["yopo"] = [(v, r, n) for v, r, n, _ in pooled]
        for key, model in (("topotraj", "topotraj"), ("agile", "agile_autonomy")):
            pts = []
            for speed in SPEEDS:
                if (condition, speed, model) in rates:
                    a, b, d, m = rates[(condition, speed, model)]
                    pts.append((speed, 100.0 * (a if kind == "success" else b) / m, m))
            curves[key] = pts
        official = []
        for speed in SPEEDS:
            bucket = ab.get((condition, "main_official", speed))
            if bucket:
                official.append((speed, 100.0 * bucket[kind] / bucket["n"], bucket["n"]))
        if official:
            curves["official"] = official
        out[condition] = curves
    return out


def render(kind, curves, path):
    label = "Success Rate [%]" if kind == "success" else "Collision Rate [%]"
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif"],
        "axes.linewidth": 1.0,
    })
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 5.0), dpi=200)
    for ax, condition in zip(axes, ("sparse", "dense")):
        for key in ("yopo", "official", "topotraj", "agile"):
            points = curves[condition].get(key)
            if not points:
                continue
            name, colour, style, marker = MODELS[key]
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            if key == "official":
                ax.plot(xs, ys, style, color=colour, marker=marker, markersize=6,
                        markerfacecolor="white", markeredgewidth=1.3, linewidth=1.6, label=name)
            else:
                ax.plot(xs, ys, style, color=colour, marker=marker, markersize=6.5,
                        linewidth=2.1 if key == "yopo" else 1.7, label=name)
        ax.set_xlim(1.4, 10.6)
        ax.set_ylim(-2, 102)
        ax.set_xticks(SPEEDS)
        ax.set_yticks([0, 20, 40, 60, 80, 100])
        ax.grid(True, color="#d9d9d9", linewidth=0.8)
        ax.set_axisbelow(True)
        ax.set_xlabel("Forward Speed [m/s]", fontsize=11)
        ax.set_ylabel(label, fontsize=11)
        ax.tick_params(labelsize=10)
    handles, labels = [], []
    for ax in axes:
        for handle, text in zip(*ax.get_legend_handles_labels()):
            if text not in labels:
                handles.append(handle)
                labels.append(text)
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.995),
               ncol=2, frameon=False, fontsize=8.6, handlelength=2.6, columnspacing=2.4, labelspacing=0.4)
    fig.text(0.29, 0.078, "(a) sparse scenario", ha="center", fontsize=11)
    fig.text(0.76, 0.078, "(b) dense scenario", ha="center", fontsize=11)
    fig.text(0.5, 0.021,
             "Solid = ROS2 frozen matrix (1,500 active slots; n = tasks per point); dashed = native A/B chain "
             "(outside the matrix: the frozen ROS2 planner rejects official weights)",
             ha="center", fontsize=7.4, color="#666666")
    fig.tight_layout(rect=(0, 0.12, 1, 0.885))
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    print("wrote", path.relative_to(ROOT).as_posix())


def markdown_tables(rates):
    lines = []
    for condition in ("sparse", "dense"):
        lines.append(f"### {condition} 成功 / 碰撞 / 超时（n=30/格；YOPO 三种子合并 n=90）\n")
        lines.append("| 模型 | " + " | ".join(f"{v} m/s" for v in SPEEDS) + " |")
        lines.append("|---|" + "---|" * len(SPEEDS))
        for key, model in (("YOPO 三种子合并", None), ("TopoTraj", "topotraj"), ("Agile Autonomy", "agile_autonomy")):
            cells = []
            for speed in SPEEDS:
                if model is None:
                    s = c = t = n = 0
                    for seed in range(3):
                        a, b, d, m = rates[(condition, speed, f"yopo_seed{seed}")]
                        s, c, t, n = s + a, c + b, t + d, n + m
                else:
                    s, c, t, n = rates[(condition, speed, model)]
                cells.append(f"{100*s/n:.0f}% / {100*c/n:.0f}% / {100*t/n:.0f}%")
            lines.append(f"| {key} | " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines)


def main():
    MEDIA.mkdir(parents=True, exist_ok=True)
    rates = matrix_rates()
    ab, ab_maps = ab_rates()
    render("success", series(rates, ab, "success"), MEDIA / "success_vs_speed.png")
    render("collision", series(rates, ab, "collision"), MEDIA / "collision_vs_speed.png")
    render_ab(ab, ab_maps, MEDIA / "official_vs_selftrained_vs_speed.png")
    print()
    print(markdown_tables(rates))
    print()
    print(ab_table(ab))


def ab_table(rates):
    """Markdown table of the native A/B batch: density x arm x speed -> S / C / T."""
    n_per_cell = max((bucket["n"] for bucket in rates.values()), default=0)
    lines = [f"### 官方 vs 自训练（原生 A/B，main 栈；每格 {n_per_cell} 架次 = 每张地图 1 架次）\n",
             "| 场景 | 权重 | " + " | ".join(f"{v} m/s" for v in SPEEDS) + " |",
             "|---|---|" + "---|" * len(SPEEDS)]
    names = {"main_official": "官方 epoch50（main 布局）", "main_local": "自训练 seed0"}
    for condition in ("sparse", "dense"):
        for arm in ("main_official", "main_local"):
            cells = []
            for speed in SPEEDS:
                bucket = rates.get((condition, arm, speed))
                cells.append("—" if not bucket else
                             f"S{bucket['success']} / C{bucket['collision']} / T{bucket['timeout']}")
            lines.append(f"| {condition} | {names[arm]} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
