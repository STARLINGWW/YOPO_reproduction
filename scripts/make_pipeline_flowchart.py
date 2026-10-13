"""Render the reproduction pipeline flowchart shown on the repository homepage.

Three bands in one figure:
  A. online inference chain (paper Fig.3 semantics: depth -> shared network ->
     15 candidates (params + scores) -> argmax -> quintic BVP -> controller);
  B. where each part lives in this repository (module numbers and entry paths);
  C. training / evaluation / acceptance chain that produces the weights and
     the evidence the inference band consumes.

Layout notes: row-A cards are evenly spaced; the closed loop is an orthogonal
path above the band (label on a white pill) so the connector area below stays
free of crossings; band-B modules reach their targets through orthogonal
elbows that share one lane.

Output: report/00_index/04_pipeline_flowchart.png (committed; regenerate with
`python scripts/make_pipeline_flowchart.py`).
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, PathPatch, Polygon
from matplotlib.path import Path as MPath

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report/00_index/04_pipeline_flowchart.png"

# --- palette ----------------------------------------------------------------
BLUE_F, BLUE_E = "#eef4fe", "#2f5fa8"
GREEN_F, GREEN_E = "#e9f6ee", "#2e7d4f"
ORANGE_F, ORANGE_E = "#fdf3e6", "#c1640d"
TITLE_C, BODY_C = "#16233a", "#4b5a72"
GREY = "#7b8798"
SHADOW = "#0f172a"


def set_cjk_font():
    from matplotlib import font_manager

    family = None
    for candidate in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/simhei.ttf"):
        if Path(candidate).is_file():
            font_manager.fontManager.addfont(candidate)
            family = family or font_manager.FontProperties(fname=candidate).get_name()
    if family:
        plt.rcParams["font.family"] = family


def box(ax, x, y, w, h, title, details, fc, ec, tfs=9.4, dfs=8.6, step=0.0225):
    """Rounded card with a bold title and centred detail lines plus a soft shadow."""
    ax.add_patch(
        FancyBboxPatch(
            (x + 0.0045, y - 0.007), w, h,
            boxstyle="round,pad=0,rounding_size=0.013",
            linewidth=0, facecolor=SHADOW, alpha=0.06, zorder=2,
        )
    )
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0,rounding_size=0.013",
            linewidth=1.6, edgecolor=ec, facecolor=fc, zorder=3,
        )
    )
    lines = [title] + list(details)
    top = y + h / 2 + (len(lines) - 1) * step / 2
    for i, text in enumerate(lines):
        ax.text(
            x + w / 2, top - i * step, text,
            ha="center", va="center", zorder=4,
            fontsize=tfs if i == 0 else dfs,
            fontweight="bold" if i == 0 else "normal",
            color=TITLE_C if i == 0 else BODY_C,
        )


def arrow(ax, x1, y1, x2, y2, color, lw=1.5, ms=13, rad=0.0, zorder=2):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=ms,
            linewidth=lw, color=color, zorder=zorder,
            connectionstyle=f"arc3,rad={rad}", shrinkA=0, shrinkB=0,
        )
    )


def elbow_up(ax, x1, y1, x2, y2, lane, color, lw=1.5, r=0.016, head=0.018, hw=0.0062):
    """Orthogonal connector from (x1, y1) up to (x2, y2) through a shared lane."""
    s = 1.0 if x2 > x1 else -1.0
    verts = [
        (x1, y1), (x1, lane - r), (x1, lane), (x1 + s * r, lane),
        (x2 - s * r, lane), (x2, lane), (x2, lane + r), (x2, y2 - head),
    ]
    codes = [
        MPath.MOVETO, MPath.LINETO, MPath.CURVE3, MPath.CURVE3,
        MPath.LINETO, MPath.CURVE3, MPath.CURVE3, MPath.LINETO,
    ]
    ax.add_patch(PathPatch(MPath(verts, codes), fill=False, edgecolor=color, linewidth=lw, zorder=2))
    ax.add_patch(
        Polygon(
            [(x2 - hw, y2 - head), (x2 + hw, y2 - head), (x2, y2)],
            closed=True, facecolor=color, edgecolor="none", zorder=2,
        )
    )


def loop_over(ax, x_start, y_start, x_end, y_end, lane, color, lw=1.5, r=0.016, head=0.018, hw=0.0062):
    """Orthogonal loop: up from (x_start, y_start), along the lane, down into
    (x_end, y_end) with a downward arrowhead."""
    s = 1.0 if x_end > x_start else -1.0
    verts = [
        (x_start, y_start), (x_start, lane - r), (x_start, lane), (x_start + s * r, lane),
        (x_end - s * r, lane), (x_end, lane), (x_end, lane - r), (x_end, y_end + head),
    ]
    codes = [
        MPath.MOVETO, MPath.LINETO, MPath.CURVE3, MPath.CURVE3,
        MPath.LINETO, MPath.CURVE3, MPath.CURVE3, MPath.LINETO,
    ]
    ax.add_patch(PathPatch(MPath(verts, codes), fill=False, edgecolor=color, linewidth=lw, zorder=2))
    ax.add_patch(
        Polygon(
            [(x_end - hw, y_end + head), (x_end + hw, y_end + head), (x_end, y_end)],
            closed=True, facecolor=color, edgecolor="none", zorder=2,
        )
    )


def band_label(ax, x, y, color, text):
    ax.add_patch(plt.Rectangle((x, y - 0.0092), 0.0068, 0.0184, facecolor=color, edgecolor="none", zorder=3))
    ax.text(x + 0.014, y, text, ha="left", va="center", fontsize=11.5, fontweight="bold", color=color, zorder=3)


def main():
    set_cjk_font()
    fig, ax = plt.subplots(figsize=(14.8, 7.9), facecolor="white")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # ---------------- header ----------------
    ax.text(.5, .972, "YOPO 复现总流程图：论文方法链 → 本地实现 → 证据与验收",
            ha="center", va="center", fontsize=18, fontweight="bold", color="#101a2e")
    ax.text(.5, .930, "一次前向传播完成规划 · 两条梯度联合训练 · 本地 Isaac Sim / ROS 2 闭环与 1500 槽协议矩阵",
            ha="center", va="center", fontsize=10.5, color=GREY)

    # ---------------- band A: online inference chain ----------------
    band_label(ax, .013, .902, BLUE_E, "在线推理（论文 Fig.3）：一次前向传播 → 选优 → 连续轨迹 → 闭环执行")
    ya, ha = .700, .132
    wa, gapa = .144, .022
    boxes_a = [
        ("深度图 + 运动状态", ["160×96 深度 · v, a, 目标 ĝ"]),
        ("共享网络", ["ResNet-18 + 1×1 预测头"]),
        ("15 组候选参数 + 15 个评分", ["偏移/终端速度加速度 · ŝ ≈ −J"]),
        ("选优", ["argmax ŝ → 终端 q*"]),
        ("连续参考轨迹", ["五次多项式（BVP · 2 s）"]),
        ("几何控制器 / Isaac", ["控制 100 Hz · 重规划 15 Hz"]),
    ]
    centers_a = []
    for i, (title, details) in enumerate(boxes_a):
        x = .013 + i * (wa + gapa)
        centers_a.append(x + wa / 2)
        box(ax, x, ya, wa, ha, title, details, BLUE_F, BLUE_E)
    for i in range(len(boxes_a) - 1):
        x1 = .013 + i * (wa + gapa) + wa
        arrow(ax, x1 + .002, ya + ha / 2, x1 + gapa - .002, ya + ha / 2, BLUE_E, lw=1.6)

    # closed loop: orthogonal path above the band, label on a white pill
    loop_over(ax, centers_a[-1], ya + ha + .004, centers_a[0], ya + ha + .002, .871, BLUE_E)
    pill_w, pill_h, px, py = .252, .0295, .5, .871
    ax.add_patch(
        FancyBboxPatch(
            (px - pill_w / 2, py - pill_h / 2), pill_w, pill_h,
            boxstyle="round,pad=0,rounding_size=0.012",
            linewidth=1.0, edgecolor="#cddbf0", facecolor="white", zorder=4,
        )
    )
    ax.text(px, py, "闭环回路：1/15 s 重读观测并重规划（通常只执行轨迹开头约 1/30）",
            ha="center", va="center", fontsize=8.4, color=BLUE_E, zorder=5)

    # ---------------- band B: repository mapping ----------------
    band_label(ax, .013, .560, GREEN_E, "本地实现（模块编号 · 位置）")
    yb, hb = .425, .115
    boxes_b = [
        (.015, .215, "① 前置与协议 01–02", ["Docker / ROS 2 准入 · 数值语义"], .205),
        (.270, .215, "③ 网络与学习 06–07", ["src/yopo_repro"], .3775),
        (.525, .215, "② 数据、代价与轨迹 03–05", ["Isaac 森林 → ESDF → 多项式"], .6325),
        (.780, .215, "④ 系统与规划 08–09", ["ros2_ws/yopo_runtime", "scripts/run_ros2_navigation.py"], .8875),
    ]
    for x, w, title, details, _ in boxes_b:
        box(ax, x, yb, w, hb, title, details, GREEN_F, GREEN_E, tfs=9.2, dfs=8.5)

    lane = .625
    targets_a = [centers_a[0], centers_a[1], centers_a[2], centers_a[5]]
    for (_, _, _, _, start_x), target in zip(boxes_b, targets_a):
        elbow_up(ax, start_x, yb + hb, target, ya, lane, GREEN_E)

    # ---------------- band C: training / evaluation / acceptance ----------------
    band_label(ax, .013, .345, ORANGE_E, "训练与验收（证据链）")
    yc, hc = .195, .115
    boxes_c = [
        (.005, .228, "数据生成 03", ["Isaac 采集 100K/10K/10K"]),
        (.259, .228, "引导训练 07", ["50 epochs × 3 seeds", "→ best_policy.pth"]),
        (.513, .228, "对照与扩展 10–11", ["专家 50 步 · TopoTraj / Agile · DAgger"]),
        (.767, .228, "验收与发布 12", ["矩阵 1500/1500 · 终审 6/6"]),
    ]
    for x, w, title, details in boxes_c:
        box(ax, x, yc, w, hc, title, details, ORANGE_F, ORANGE_E, tfs=9.2, dfs=8.5)
    for i in range(len(boxes_c) - 1):
        x1 = boxes_c[i][0] + boxes_c[i][1]
        arrow(ax, x1 + .002, yc + hc / 2, boxes_c[i + 1][0] - .002, yc + hc / 2, ORANGE_E, lw=1.6)

    # weights feed the online network
    c2 = boxes_c[1][0] + boxes_c[1][1] / 2
    arrow(ax, c2, yc + hc + .003, c2, yb - .002, ORANGE_E, lw=1.7)
    ax.text(c2 + .010, (yc + hc + yb) / 2, "权重供在线推理", ha="left", va="center",
            fontsize=8.8, color=ORANGE_E)

    # ---------------- footer ----------------
    ax.plot([.013, .987], [.107, .107], color="#e2e8f0", linewidth=1.2, zorder=1)
    ax.text(.013, .072,
            "论文对应：Fig.3 与式 (3)–(9)（推理）· II-B Guidance Learning（训练）。"
            "模块逐一说明见 report/00_index/01_module_map.md；精读笔记与自绘原理图见 report/02_method/reading_note/。",
            fontsize=9.0, color=GREY, ha="left", va="center")

    fig.tight_layout(rect=(0, 0, 1, 1))
    fig.savefig(OUT, dpi=190, facecolor="white", bbox_inches="tight")
    print("wrote", OUT.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
