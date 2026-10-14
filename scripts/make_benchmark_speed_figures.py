"""Render the paper-aligned success / collision figures for the project-map page.

Frozen, read-only evidence sources:
  * artifacts/benchmark_summary/summary.json - active 1,500-slot ROS2 matrix.
      - subset "all30"       : n = 30 tasks per model x density x speed
                               (self-trained proposed pooled over 3 seeds -> n = 90);
      - subset "paper_first10": the first 10 tasks of the same cells - the size the
                               paper reports for Fig. 7 ("10 repeats per condition").
  * report/00_index/media/paper_fig7_digitized.json - the paper's own Fig. 7 values,
      digitized from artifacts/paper_sources/YOPO_author_version.pdf (page 6) with the
      axes calibrated on the tick marks and per-series pixels extracted by colour.
      Values lie on the 10 % grid, consistent with 10 repeats per condition.
  * artifacts/weights_ab_demo/batch_summary.json - native official-vs-self-trained A/B
      (kept as a printed table; no longer drawn - the paper has no counterpart, and the
      comparison figure is now the paper-scale alignment).
  * artifacts/benchmark_summary/reference_arm_official_v1_summary.json - optional: the
      same-chain external-reference arm (official epoch50 weights, hash-pinned). When the
      summary exists its success/collision curves are drawn into both matrix figures so
      the comparison is "official vs self-trained under the same chain, criteria and n";
      while the 300-slot run is still in progress the curve carries the live count.

Figures (regenerate with `python scripts/make_benchmark_speed_figures.py`):
  report/00_index/media/success_vs_speed.png    - Fig.7 layout, success rate; solid =
      full frozen matrix, dashed = paper-scale first10 subset (same three methods).
  report/00_index/media/collision_vs_speed.png  - same layout, collision rate.
  report/00_index/media/paper_vs_reproduction_vs_speed.png - our paper-scale curves vs
      the paper's digitized Fig. 7 curves (success rate; MPPI archived on our side).
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
PAPER_FIG7 = ROOT / "report/00_index/media/paper_fig7_digitized.json"
REFERENCE_SUMMARY = ROOT / "artifacts/benchmark_summary/reference_arm_official_v1_summary.json"
MEDIA = ROOT / "report/00_index/media"

SPEEDS = [2, 4, 6, 8, 10]
CONDITIONS = {"sparse": "sparse  (\u03c1 = 1/30 m$^{-2}$)", "dense": "dense  (\u03c1 = 1/20 m$^{-2}$)"}
MODELS = {
    "yopo": ("Proposed", "#b2182b", "o"),
    "topotraj": ("TopoTraj", "#1b9e77", "^"),
    "agile": ("Agile Autonomy", "#e08214", "D"),
}


def _rates(subset):
    """(condition, speed) -> {model: (success, collision, timeout, n)} for one subset."""
    data = json.loads(SUMMARY.read_text(encoding="utf-8"))
    rates = {}
    for group in data["groups"]:
        if group.get("subset") != subset:
            continue
        per_speed = rates.setdefault((group["condition"], int(group["speed_mps"])), {})
        outcomes = group["outcomes"]
        per_speed[group["model"]] = (
            outcomes.get("success", 0), outcomes.get("collision", 0),
            outcomes.get("timeout", 0), group["completed"],
        )
    return rates


def matrix_rates():
    return _rates("all30")


def first10_rates():
    return _rates("paper_first10")


def reference_rates():
    """(condition, speed) -> (success, collision, timeout, completed, expected) or {} if absent."""
    if not REFERENCE_SUMMARY.is_file():
        return {}
    data = json.loads(REFERENCE_SUMMARY.read_text(encoding="utf-8"))
    rates = {}
    for group in data.get("groups", []):
        if group.get("subset") != "all30":
            continue
        outcomes = group.get("outcomes", {})
        rates[(group["condition"], group["speed_mps"])] = (
            outcomes.get("success", 0), outcomes.get("collision", 0), outcomes.get("timeout", 0),
            group["completed"], group["expected"])
    return rates


def series(rates, kind):
    """{condition: {model_key: [(speed, rate%, n), ...]}} for 'success' or 'collision'."""
    out = {}
    for condition in CONDITIONS:
        curves = {}
        pooled = []
        for speed in SPEEDS:
            per_speed = rates.get((condition, speed), {})
            s = c = n = 0
            for seed in range(3):
                if f"yopo_seed{seed}" in per_speed:
                    a, b, d, m = per_speed[f"yopo_seed{seed}"]
                    s, c, n = s + a, c + b, n + m
            pooled.append((speed, 100.0 * (s if kind == "success" else c) / n, n))
        curves["yopo"] = pooled
        for key, model in (("topotraj", "topotraj"), ("agile", "agile_autonomy")):
            pts = []
            for speed in SPEEDS:
                if model in rates.get((condition, speed), {}):
                    a, b, d, m = rates[(condition, speed)][model]
                    pts.append((speed, 100.0 * (a if kind == "success" else b) / m, m))
            curves[key] = pts
        out[condition] = curves
    return out


def _style():
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif"],
        "axes.linewidth": 1.0,
    })


def _axes(ax, ylabel):
    ax.set_xlim(1.4, 10.6)
    ax.set_ylim(-2, 102)
    ax.set_xticks(SPEEDS)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.grid(True, color="#d9d9d9", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel("Forward Speed [m/s]", fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.tick_params(labelsize=10)


def render(kind, full, paper_scale, reference, path):
    """Fig.7 layout: solid = full frozen matrix, dashed = paper-scale first10 subset;
    the external-reference arm (official weights, same chain) is drawn when its summary exists."""
    label = "Success Rate [%]" if kind == "success" else "Collision Rate [%]"
    ref_index = 0 if kind == "success" else 1
    ref_completed = sum(v[3] for v in reference.values())
    ref_expected = sum(v[4] for v in reference.values())
    ref_label = ("Official epoch50 - reference arm (n=30/point)"
                 if reference and ref_completed >= ref_expected
                 else "Official epoch50 - reference arm (running: %d/%d slots)" % (ref_completed, ref_expected))
    _style()
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 5.0), dpi=200)
    for ax, condition in zip(axes, ("sparse", "dense")):
        for key in ("yopo", "topotraj", "agile"):
            name, colour, marker = MODELS[key]
            points = full[condition].get(key) or []
            if points:
                ax.plot([p[0] for p in points], [p[1] for p in points], "-",
                        color=colour, marker=marker, markersize=6.5,
                        linewidth=2.1 if key == "yopo" else 1.7,
                        label=f"{name} - full matrix (n={points[0][2]})")
            points = paper_scale[condition].get(key) or []
            if points:
                ax.plot([p[0] for p in points], [p[1] for p in points], "--",
                        color=colour, marker=marker, markersize=6,
                        markerfacecolor="white", markeredgewidth=1.3,
                        linewidth=1.6, label=f"{name} - paper-scale (n={points[0][2]})")
        ref_points = [(speed, 100.0 * reference[(condition, speed)][ref_index] / reference[(condition, speed)][3], reference[(condition, speed)][3])
                      for speed in SPEEDS
                      if (condition, speed) in reference and reference[(condition, speed)][3] > 0]
        if ref_points:
            ax.plot([p[0] for p in ref_points], [p[1] for p in ref_points], "-",
                    color="#2166ac", marker="s", markersize=6, linewidth=1.9, label=ref_label)
        _axes(ax, label)
    handles, labels = [], []
    for ax in axes:
        for handle, text in zip(*ax.get_legend_handles_labels()):
            if text not in labels:
                handles.append(handle)
                labels.append(text)
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.995),
               ncol=3, frameon=False, fontsize=8.2, handlelength=2.4, columnspacing=1.8,
               labelspacing=0.35)
    fig.text(0.29, 0.078, "(a) sparse scenario", ha="center", fontsize=11)
    fig.text(0.76, 0.078, "(b) dense scenario", ha="center", fontsize=11)
    footer = ("Solid = full ROS2 frozen matrix (1,500 active slots); dashed = paper-scale subset "
              "(first10 tasks, matching the paper's 10 repeats per condition)")
    if reference:
        footer += "; blue = official epoch50 reference arm (same chain, external_reference class)"
    fig.text(0.5, 0.021, footer, ha="center", fontsize=7.4, color="#666666")
    fig.tight_layout(rect=(0, 0.12, 1, 0.89))
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    print("wrote", path.relative_to(ROOT).as_posix())


def render_paper_alignment(paper_scale, paper, path):
    """Ours (paper-scale first10) vs the paper's digitized Fig. 7 (success rate)."""
    _style()
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 5.0), dpi=200)
    for ax, condition in zip(axes, ("sparse", "dense")):
        for key in ("yopo", "topotraj", "agile"):
            name, colour, marker = MODELS[key]
            points = paper_scale[condition].get(key) or []
            if points:
                ax.plot([p[0] for p in points], [p[1] for p in points], "-",
                        color=colour, marker=marker, markersize=6.5,
                        linewidth=2.1 if key == "yopo" else 1.7,
                        label=f"{name} - ours, paper-scale (n={points[0][2]})")
            paper_key = {"yopo": "Proposed", "topotraj": "TopoTraj", "agile": "Agile"}[key]
            values = paper["scenarios"][condition][paper_key]
            ax.plot(SPEEDS, values, "--", color=colour, marker=marker, markersize=6,
                    markerfacecolor="white", markeredgewidth=1.3, linewidth=1.5,
                    label=f"{name} - paper Fig.7 (n={paper['n_per_point']})")
        _axes(ax, "Success Rate [%]")
    handles, labels = [], []
    for ax in axes:
        for handle, text in zip(*ax.get_legend_handles_labels()):
            if text not in labels:
                handles.append(handle)
                labels.append(text)
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.995),
               ncol=3, frameon=False, fontsize=8.0, handlelength=2.4, columnspacing=1.8,
               labelspacing=0.35)
    fig.text(0.29, 0.078, "(a) sparse scenario", ha="center", fontsize=11)
    fig.text(0.76, 0.078, "(b) dense scenario", ha="center", fontsize=11)
    fig.text(0.5, 0.021,
             "Solid = this reproduction, paper-scale subset (first10 tasks; proposed pooled over "
             "3 seeds); dashed = values digitized from the paper's Fig. 7 (page 6; 10 % grid). "
             "MPPI is archived on our side and not drawn.",
             ha="center", fontsize=7.2, color="#666666")
    fig.tight_layout(rect=(0, 0.12, 1, 0.89))
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    print("wrote", path.relative_to(ROOT).as_posix())


def ab_rates():
    """(condition, arm, speed) -> (success, collision, timeout, n) from the native A/B batch."""
    data = json.loads(AB_BATCH.read_text(encoding="utf-8"))
    rates = {}
    for record in data["records"]:
        if not record["arm"].startswith("main_"):
            continue
        density = record.get("scene_density_per_m2")
        if density is None:
            continue
        condition = "sparse" if density < 0.04 else "dense"
        key = (condition, record["arm"], int(record["speed_mps"]))
        bucket = rates.setdefault(key, {"success": 0, "collision": 0, "timeout": 0, "n": 0})
        bucket["success"] += record["status"] == "success"
        bucket["collision"] += record["status"] == "collision"
        bucket["timeout"] += record["status"] == "timeout"
        bucket["n"] += 1
    return rates


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


def main():
    MEDIA.mkdir(parents=True, exist_ok=True)
    full = matrix_rates()
    paper_scale = first10_rates()
    reference = reference_rates()
    render("success", series(full, "success"), series(paper_scale, "success"), reference,
           MEDIA / "success_vs_speed.png")
    render("collision", series(full, "collision"), series(paper_scale, "collision"), reference,
           MEDIA / "collision_vs_speed.png")
    render_paper_alignment(series(paper_scale, "success"),
                           json.loads(PAPER_FIG7.read_text(encoding="utf-8")),
                           MEDIA / "paper_vs_reproduction_vs_speed.png")
    print()
    print(ab_table(ab_rates()))


if __name__ == "__main__":
    main()
