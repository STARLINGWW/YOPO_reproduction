"""Render the reproduction pipeline flowchart shown on the repository homepage.

Three bands in one figure:
  A. online inference chain (paper Fig.3 semantics: depth -> shared network ->
     15 candidates (params + scores) -> argmax -> quintic BVP -> controller);
  B. where each part lives in this repository (module numbers and entry paths);
  C. training / evaluation / acceptance chain that produces the weights and
     the evidence the inference band consumes.

Output: report/00_index/04_pipeline_flowchart.png (committed; regenerate with
`python scripts/make_pipeline_flowchart.py`).
"""
from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report/00_index/04_pipeline_flowchart.png"

C_BLUE, C_BLUE_E = "#e8f0fe", "#1a56b0"
C_GREEN, C_GREEN_E = "#e6f6ec", "#1e7a44"
C_ORANGE, C_ORANGE_E = "#fff1e0", "#c0630a"
C_GREY = "#5a6472"


def set_cjk_font():
    from matplotlib import font_manager
    for candidate in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/simhei.ttf"):
        if Path(candidate).is_file():
            font_manager.fontManager.addfont(candidate)
            plt.rcParams["font.family"] = font_manager.FontProperties(fname=candidate).get_name()
            return


def box(ax, x, y, w, h, text, fc, ec, fontsize=10.5, bold_first=True):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.008,rounding_size=0.012",
                                linewidth=1.4, edgecolor=ec, facecolor=fc, zorder=3))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize,
            color="#1c2430", zorder=4, linespacing=1.45)


def arrow(ax, x1, y1, x2, y2, color="#40506a", lw=1.8, style="-|>", rad=0.0):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=14,
                                 linewidth=lw, color=color, zorder=2,
                                 connectionstyle=f"arc3,rad={rad}"))


def main():
    set_cjk_font()
    fig, ax = plt.subplots(figsize=(14.8, 7.9), facecolor="white")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    ax.text(.5, .975, "YOPO 复现总流程图：论文方法链 → 本地实现 → 证据与验收",
            ha="center", va="center", fontsize=17, fontweight="bold", color="#111827")
    ax.text(.5, .935, "一次前向传播完成规划 · 两条梯度联合训练 · 本地 Isaac Sim / ROS 2 闭环与 1500 槽协议矩阵",
            ha="center", va="center", fontsize=11, color=C_GREY)

    # ---------------- Band A: online inference chain (6 boxes) ----------------
    ax.text(.015, .900, "在线推理（论文 Fig.3）：一次前向传播 → 选优 → 连续轨迹 → 闭环执行",
            fontsize=12, fontweight="bold", color=C_BLUE_E)
    yA, hA = .695, .135
    boxes_a = [
        (.020, .145, "深度图 + 运动状态\n160×96 深度；v, a, 目标 ĝ"),
        (.181, .150, "共享网络\nResNet-18 + 1×1 预测头"),
        (.347, .175, "15 组候选参数 + 15 个评分\n偏移/终端速度加速度；ŝ ≈ −J"),
        (.538, .130, "选优\nargmax ŝ → 终端 q*"),
        (.684, .150, "连续参考轨迹\n五次多项式（BVP，2 s）"),
        (.850, .145, "几何控制器 / Isaac\n控制 100 Hz · 重规划 15 Hz"),
    ]
    for x, w, text in boxes_a:
        box(ax, x, yA, w, hA, text, C_BLUE, C_BLUE_E, fontsize=9.5)
    for (x1, w1, _), (x2, _, _) in zip(boxes_a, boxes_a[1:]):
        arrow(ax, x1 + w1, yA + hA / 2, x2, yA + hA / 2, C_BLUE_E)
    arrow(ax, .9225, yA, .2555, yA, C_BLUE_E, rad=-.14, lw=1.4)
    ax.text(.60, .607, "闭环回路：1/15 s 重读观测并重规划（2 s 轨迹通常只执行开头约 1/30）",
            fontsize=8.8, color=C_BLUE_E, ha="center")

    # ---------------- Band B: repository mapping ----------------
    ax.text(.015, .560, "本地实现（模块编号 · 位置）", fontsize=12, fontweight="bold", color=C_GREEN_E)
    yB, hB = .425, .115
    boxes_b = [
        (.020, .230, "① 前置与协议 01–02\nDocker / ROS 2 准入 · 数值语义"),
        (.280, .190, "③ 网络与学习 06–07\nsrc/yopo_repro"),
        (.500, .205, "② 数据、代价与轨迹 03–05\nIsaac 森林 → ESDF → 多项式"),
        (.735, .245, "④ 系统与规划 08–09\nros2_ws/yopo_runtime\nscripts/run_ros2_navigation.py"),
    ]
    for x, w, text in boxes_b:
        box(ax, x, yB, w, hB, text, C_GREEN, C_GREEN_E, fontsize=9.2)
    arrow(ax, .135, yB + hB, .0925, yA, C_GREEN_E, lw=1.4)
    arrow(ax, .375, yB + hB, .30, yA, C_GREEN_E, lw=1.4)
    arrow(ax, .6025, yB + hB, .50, yA, C_GREEN_E, lw=1.4)
    arrow(ax, .8575, yB + hB, .9225, yA, C_GREEN_E, lw=1.4)

    # ---------------- Band C: training / evaluation / acceptance ----------------
    ax.text(.015, .345, "训练与验收（证据链）", fontsize=12, fontweight="bold", color=C_ORANGE_E)
    yC, hC = .195, .115
    boxes_c = [
        (.020, .215, "数据生成 03\nIsaac 采集 100K/10K/10K"),
        (.265, .225, "引导训练 07\n50 epochs ×3 seeds\n→ best_policy.pth"),
        (.520, .225, "对照与扩展 10–11\n专家 50 步 · TopoTraj/Agile · DAgger"),
        (.775, .205, "验收与发布 12\n矩阵 1500/1500 · 终审 6/6"),
    ]
    for x, w, text in boxes_c:
        box(ax, x, yC, w, hC, text, C_ORANGE, C_ORANGE_E, fontsize=9.2)
    for (x1, w1, _), (x2, _, _) in zip(boxes_c, boxes_c[1:]):
        arrow(ax, x1 + w1, yC + hC / 2, x2, yC + hC / 2, C_ORANGE_E)
    arrow(ax, .3775, yC + hC, .375, yB, C_ORANGE_E, lw=1.6)
    ax.text(.388, .355, "权重供在线推理", fontsize=9, color=C_ORANGE_E, ha="left")

    ax.text(.015, .055, "论文对应：Fig.3 与式 (3)–(9)（推理）· II-B Guidance Learning（训练）。"
                        "模块逐一说明见 report/00_index/01_module_map.md；精读笔记与自绘原理图见 report/02_method/reading_note/。",
            fontsize=9.2, color=C_GREY)
    fig.tight_layout(rect=(0, 0, 1, 1))
    fig.savefig(OUT, dpi=170, facecolor="white", bbox_inches="tight")
    print("wrote", OUT.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
