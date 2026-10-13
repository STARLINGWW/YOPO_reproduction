"""Generate the primitive-offset geometry diagrams (educational; no network output).

Outputs, all written to ../assets/
  05_primitive_offset_geometry.png   combined 3-panel sheet (note / handout)
  05a_primitive_sector.png           slide panel: spherical lattice + sector
  05b_primitive_section.png          slide panel: top-down angle/radius section
  05c_frame_rotation.png             slide panel: where R_ij acts

The slide panels carry larger type so they stay legible when scaled onto a
16:9 slide; the combined sheet packs the same content for reading.

Numbers follow the paper's Eq. (3)(4)(6)(7)(8)(9) plus the author config
(r = 4 m, anchor FOV 30 deg, v_max = 6 m/s, T = 2r/v_max). The orange endpoint
is a hand-picked illustration, not a network prediction.
"""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge, Arc, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets"
OUT.mkdir(exist_ok=True)

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False
# A CJK font carries no math glyphs, so keep mathtext on its own font set.
plt.rcParams["mathtext.fontset"] = "dejavusans"

INK, MUTED = "#18304A", "#596C80"
BLUE, GREEN, ORANGE, PURPLE = "#2377B8", "#14866E", "#C77022", "#7961B3"
GRAY, BG = "#A4AFBB", "#F7F9FC"

# ----------------------------------------------------------------- config
R_ANCHOR = 4.0
R_MAX = 2 * R_ANCHOR
V_MAX = 6.0
SEG_T = 2 * R_ANCHOR / V_MAX
D_PHI = D_TH = 15.0
PHI = np.array([-36.0, -18.0, 0.0, 18.0, 36.0])
TH = np.array([-20.0, 0.0, 20.0])
PHI_ILL, TH_ILL, R_ILL = 10.0, 7.0, 6.4


# ============================================================ panel drawings
def draw_sector_3d(ax, fs=1.0, labels=True):
    """Spherical lattice of 15 anchors plus the reachable sector of one."""
    for th in TH:
        a, b = np.radians(PHI), np.radians(th)
        ax.scatter(R_ANCHOR * np.cos(b) * np.cos(a),
                   R_ANCHOR * np.cos(b) * np.sin(a),
                   np.full(len(a), R_ANCHOR * np.sin(b)),
                   s=26 * fs, color=GRAY, depthshade=False, zorder=5)

    ph = np.radians(np.linspace(-D_PHI, D_PHI, 40))
    tt = np.radians(np.linspace(-D_TH, D_TH, 40))
    PH, TT = np.meshgrid(ph, tt)
    ax.plot_surface(R_MAX * np.cos(TT) * np.cos(PH), R_MAX * np.cos(TT) * np.sin(PH),
                    R_MAX * np.sin(TT), color=BLUE, alpha=0.22, linewidth=0,
                    antialiased=True, shade=False)

    for s_ph, s_th in [(-D_PHI, -D_TH), (-D_PHI, D_TH), (D_PHI, -D_TH), (D_PHI, D_TH)]:
        p, t = np.radians(s_ph), np.radians(s_th)
        ax.plot([0, R_MAX * np.cos(t) * np.cos(p)], [0, R_MAX * np.cos(t) * np.sin(p)],
                [0, R_MAX * np.sin(t)], color=BLUE, lw=0.9, alpha=0.55, zorder=4)
    rim = np.radians(np.linspace(-D_PHI, D_PHI, 80))
    ax.plot(R_MAX * np.cos(rim), R_MAX * np.sin(rim), np.zeros_like(rim),
            color=BLUE, lw=1.6, zorder=5)

    px = R_ILL * np.cos(np.radians(TH_ILL)) * np.cos(np.radians(PHI_ILL))
    py = R_ILL * np.cos(np.radians(TH_ILL)) * np.sin(np.radians(PHI_ILL))
    pz = R_ILL * np.sin(np.radians(TH_ILL))
    ax.quiver(0, 0, 0, R_ANCHOR, 0, 0, color=BLUE, linewidth=2.4,
              arrow_length_ratio=0.12, zorder=8)
    ax.quiver(0, 0, 0, px, py, pz, color=ORANGE, linewidth=2.6,
              arrow_length_ratio=0.12, zorder=9)
    ax.scatter([px], [py], [pz], s=64 * fs, color=ORANGE, depthshade=False, zorder=10)

    L = 8.6
    for vec, lab, off in [((L, 0, 0), "$x$  前", (0.2, -0.9, 0.0)),
                          ((0, L * 0.60, 0), "$y$  左", (0.2, 0.4, 0.0)),
                          ((0, 0, L * 0.62), "$z$  上", (0.2, 0.2, 0.0))]:
        ax.quiver(0, 0, 0, *vec, color=GRAY, linewidth=1.0, arrow_length_ratio=0.08)
        ax.text(vec[0] + off[0], vec[1] + off[1], vec[2] + off[2], lab,
                color=INK, fontsize=10 * fs)

    if labels:
        ax.text(px + 0.3, py + 0.6, pz + 1.0, "预测终点 $\\mathbf{p}_T$",
                color=ORANGE, fontsize=10.5 * fs)
        ax.text2D(0.075, 0.075, "$r=4$ m：锚点\n（15 个灰点）",
                  transform=ax.transAxes, color=BLUE, fontsize=9.5 * fs, linespacing=1.6)
        ax.text2D(0.655, 0.80,
                  "可达扇区\n$r'\\in(0,\\,8)$ m\n角度各 $\\pm15^\\circ$",
                  transform=ax.transAxes, color=BLUE, fontsize=9.5 * fs, linespacing=1.7)

    ax.set_xlim(-3.0, 9.2)
    ax.set_ylim(-6.2, 6.2)
    ax.set_zlim(-3.2, 5.4)
    ax.view_init(elev=22, azim=-74)
    ax.set_box_aspect((12.2, 12.4, 8.6), zoom=1.62)
    ax.set_axis_off()


def draw_section(ax, fs=1.0, labels=True):
    """Top-down section: anchor spacing, +/-15 deg window, 12 deg overlap."""
    ax.set_facecolor(BG)
    ax.set_xlim(-6.2, 10.4)
    ax.set_ylim(-6.6, 6.8)
    ax.set_aspect("equal")
    ax.axis("off")

    for phi0, colour in [(18.0, GREEN), (-18.0, ORANGE)]:
        ax.add_patch(Wedge((0, 0), R_MAX, phi0 - D_PHI, phi0 + D_PHI,
                           facecolor=colour, alpha=0.09, edgecolor="none", zorder=1))
    ax.add_patch(Wedge((0, 0), R_MAX, -D_PHI, D_PHI,
                       facecolor=BLUE, alpha=0.15, edgecolor="none", zorder=2))

    for angle, colour in [(-D_PHI, BLUE), (D_PHI, BLUE),
                          (18.0 - D_PHI, GREEN), (18.0 + D_PHI, GREEN),
                          (-18.0 - D_PHI, ORANGE), (-18.0 + D_PHI, ORANGE)]:
        ax.plot([0, R_MAX * np.cos(np.radians(angle))],
                [0, R_MAX * np.sin(np.radians(angle))],
                color=colour, lw=1.0, ls=(0, (5, 3)), zorder=3)

    ax.add_patch(Arc((0, 0), 2 * R_ANCHOR, 2 * R_ANCHOR, theta1=-56, theta2=56,
                     color=BLUE, lw=1.6, zorder=4))
    ax.add_patch(Arc((0, 0), 2 * R_MAX, 2 * R_MAX, theta1=-27, theta2=27,
                     color=BLUE, lw=1.6, zorder=4))

    for p in PHI:
        ax.plot([0, R_ANCHOR * np.cos(np.radians(p))],
                [0, R_ANCHOR * np.sin(np.radians(p))],
                color=GRAY, lw=1.3, zorder=4)
        ax.scatter([R_ANCHOR * np.cos(np.radians(p))],
                   [R_ANCHOR * np.sin(np.radians(p))], s=20 * fs, color=GRAY, zorder=5)

    ax.plot([0, R_ILL * np.cos(np.radians(PHI_ILL))],
            [0, R_ILL * np.sin(np.radians(PHI_ILL))], color=ORANGE, lw=2.3, zorder=6)
    ax.scatter([R_ILL * np.cos(np.radians(PHI_ILL))],
               [R_ILL * np.sin(np.radians(PHI_ILL))], s=46 * fs, color=ORANGE, zorder=7)

    ax.annotate("", xy=(3.9 * np.cos(np.radians(D_PHI)), 3.9 * np.sin(np.radians(D_PHI))),
                xytext=(3.9, 0.0),
                arrowprops=dict(arrowstyle="->", color=PURPLE, lw=1.5,
                                connectionstyle="arc3,rad=0.3"), zorder=8)
    ax.text(4.35, 1.5, "$\\Delta\\varphi$", color=PURPLE, fontsize=11.5 * fs)
    ax.annotate("", xy=(5.6 * np.cos(np.radians(PHI_ILL)), 5.6 * np.sin(np.radians(PHI_ILL))),
                xytext=(3.1 * np.cos(np.radians(PHI_ILL)), 3.1 * np.sin(np.radians(PHI_ILL))),
                arrowprops=dict(arrowstyle="->", color=ORANGE, lw=1.5), zorder=8)
    ax.text(4.85, 0.95, "$\\Delta r$", color=ORANGE, fontsize=11.5 * fs)

    ax.text(2.05, -1.85, "$r=4$ m", color=BLUE, fontsize=9.5 * fs)
    if not labels:
        return
    ax.text(-6.0, 6.1, "$\\varphi_i=0^\\circ$（本例）", color=GRAY, fontsize=9.5 * fs)
    ax.text(6.2, 4.6, "相邻锚点窗口\n重叠 $12^\\circ$", color=GREEN,
            fontsize=9.5 * fs, linespacing=1.5)
    ax.text(-6.0, -6.3, "扇区半径上限 $r'_{\\max}=8$ m\n"
                        "$=$ 全程 $v_{\\max}$ 直飞 $T$ 秒",
            color=MUTED, fontsize=9.0 * fs, linespacing=1.5)


def draw_rotation(ax, fs=1.0, labels=True):
    """Top-down view of the rotation plus the formula box."""
    ax.set_facecolor(BG)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")

    ins = ax.inset_axes([0.00, 0.04, 0.46, 0.90])
    ins.set_facecolor(BG)
    ins.set_xlim(-0.9, 4.6)
    ins.set_ylim(-0.9, 4.6)
    ins.set_aspect("equal")
    ins.axis("off")

    O = (0.9, 0.9)
    PHI_F = 34.0
    axis_len, vec_len = 2.5, 2.0
    for ang, lab, colour, dx, dy in [(0.0, "$x_b$", INK, 0.14, -0.40 * fs),
                                     (90.0, "$y_b$", INK, 0.06, 0.16 * fs),
                                     (PHI_F, "$x_p$", PURPLE, 0.10, -0.40 * fs),
                                     (PHI_F + 90.0, "$y_p$", PURPLE, 0.10, 0.16 * fs)]:
        e = np.radians(ang)
        ins.annotate("", xy=(O[0] + axis_len * np.cos(e), O[1] + axis_len * np.sin(e)),
                     xytext=O, arrowprops=dict(arrowstyle="-|>", color=colour, lw=1.7))
        ins.text(O[0] + (axis_len + 0.05) * np.cos(e) + dx,
                 O[1] + (axis_len + 0.05) * np.sin(e) + dy, lab,
                 fontsize=10 * fs, color=colour)

    ins.add_patch(Arc(O, 1.35, 1.35, theta1=0, theta2=90, color=GRAY,
                      lw=1.0, ls=(0, (3, 3)), zorder=1))
    ins.add_patch(Arc(O, 0.95, 0.95, theta1=0, theta2=PHI_F, color=PURPLE,
                      lw=1.2, zorder=1))
    ins.text(O[0] + 0.60, O[1] + 0.22, "$\\varphi_i$", fontsize=10 * fs, color=PURPLE)

    e = np.radians(PHI_F * 0.5)
    tip = (O[0] + vec_len * np.cos(e), O[1] + vec_len * np.sin(e))
    ins.annotate("", xy=tip, xytext=O,
                 arrowprops=dict(arrowstyle="-|>", color=ORANGE, lw=2.7))
    ins.text(tip[0] - 0.85, tip[1] + 0.18, "$\\mathbf{v}_T$",
             fontsize=12 * fs, color=ORANGE)
    ins.text(O[0] - 0.78, O[1] - 0.62, "机体系原点", fontsize=9 * fs, color=MUTED)

    if not labels:
        return
    ax.add_patch(FancyBboxPatch((4.62, 0.85), 5.24, 8.3,
                                boxstyle="round,pad=0.16", facecolor="white",
                                edgecolor=GRAY, lw=1.0))
    ax.text(4.9, 8.35, "$\\mathbf{v}_T=R_{ij}\\,\\tanh(\\mathbf{y}_v)\\,v_{\\max}$",
            fontsize=11 * fs, color=ORANGE)
    ax.text(4.9, 7.60, "$R_{ij}=R_z(\\varphi_i)\\,R_y(-\\theta_j)$",
            fontsize=10 * fs, color=INK)
    ax.text(4.9, 6.65, "① 网络在基元系里输出终端速度/加速度；",
            fontsize=8.6 * fs, color=MUTED)
    ax.text(4.9, 6.05, "② 乘 $v_{\\max}$/$a_{\\max}$ 后旋转回机体系。",
            fontsize=8.6 * fs, color=MUTED)
    ax.text(4.9, 4.95, "状态输入走反向：", fontsize=8.6 * fs, color=MUTED)
    ax.text(4.9, 4.35, "$\\mathbf{x}'_{ij}=R_{ij}^{-1}\\mathbf{x}$",
            fontsize=10 * fs, color=GREEN)
    ax.text(4.9, 3.25, "位置不参与旋转，直接在机体系合成：",
            fontsize=8.6 * fs, color=MUTED)
    ax.text(4.9, 2.65, "$\\mathbf{p}_T$ 由 $(r',\\theta',\\varphi')$ 直接算出",
            fontsize=9.5 * fs, color=GREEN)
    ax.text(4.9, 1.45, "所以旋转只影响终端导数，不影响终点位置。",
            fontsize=8.6 * fs, color=INK)


# ============================================================ combined sheet
fig = plt.figure(figsize=(12.6, 8.2), dpi=150, facecolor=BG)
gs = fig.add_gridspec(2, 5, left=0.03, right=0.975, top=0.855, bottom=0.075,
                      wspace=0.34, hspace=0.36)
fig.text(0.03, 0.955, "运动基元的球面修正量与坐标系转换",
         fontsize=17, color=INK, weight="bold")
fig.text(0.03, 0.913,
         "锚点固定、修正有界。位置直接在机体系下用球坐标合成；"
         "只有终端速度与加速度需要从基元系旋转回机体系。",
         fontsize=10.5, color=MUTED)

ax_a = fig.add_subplot(gs[:, 0:3], projection="3d")
ax_a.set_facecolor(BG)
draw_sector_3d(ax_a, fs=1.0)
ax_a.set_title("(a) 球面格点与单个锚点的可达扇区", fontsize=11.5, color=INK, pad=-2)

ax_b = fig.add_subplot(gs[0, 3:5])
draw_section(ax_b, fs=1.0)
ax_b.set_title("(b) 水平剖面：角度窗口与半径修正", fontsize=11.5, color=INK, pad=4)

ax_c = fig.add_subplot(gs[1, 3:5])
draw_rotation(ax_c, fs=1.0)
ax_c.set_title("(c) 基元系与机体系：$R_{ij}$ 作用在哪里", fontsize=11.5, color=INK, pad=4)

fig.text(0.03, 0.022,
         "数据来源：原文式 (3)(4)(6)(7)(8)(9)；半径 r = 4 m、锚点 FOV 30°、"
         f"$v_{{\\max}}$ = 6 m/s、$T$ = 2r/$v_{{\\max}}$ = {SEG_T:.2f} s。"
         "橙线终点与旋转角为教学构造，不是网络实际输出。",
         fontsize=8.6, color=MUTED)
combined = OUT / "05_primitive_offset_geometry.png"
fig.savefig(combined, facecolor=BG)
print("written:", combined)

# ============================================================ slide panels
# A slide fills its text width with the figure, so a near-square panel would be
# squeezed to unreadable type. These variants use a wide 2.2:1 layout with a
# large-type caption column, which keeps the projected text legible.
SLIDE_FS = 12.5
SLIDE_TITLE = 15.5
W, H = 7.9, 3.6


def slide_shell(title):
    """Slide panels carry no internal title: the beamer frame supplies it."""
    return plt.figure(figsize=(W, H), dpi=170, facecolor=BG)


def caption_column(f, lines, x=0.545, y=0.70, dy=0.135, fs=SLIDE_FS):
    """lines: list of (text, colour) tuples."""
    for i, (txt, colour) in enumerate(lines):
        f.text(x, y - i * dy, txt, fontsize=fs, color=colour, linespacing=1.5)


# ---- (a) spherical lattice + reachable sector
f = slide_shell("(a) 球面格点与单个锚点的可达扇区")
a = f.add_axes([-0.005, 0.01, 0.58, 0.97], projection="3d")
a.set_facecolor(BG)
draw_sector_3d(a, fs=1.6, labels=False)
a.set_title("")
caption_column(f, [
    ("15 个锚点：方向固定", BLUE),
    ("$5\\times3$，$r=4$ m", BLUE),
    ("", BLUE),
    ("单个锚点的可达扇区", BLUE),
    ("$r'\\in(0,\\,8)$ m", BLUE),
    ("角度各 $\\pm15^\\circ$", BLUE),
    ("", BLUE),
    ("橙线：网络预测的终点", ORANGE),
], x=0.615, y=0.80, dy=0.125, fs=SLIDE_FS)
f.savefig(OUT / "05a_primitive_sector.png", facecolor=BG)
print("written:", OUT / "05a_primitive_sector.png")
plt.close(f)

# ---- (b) top-down section
f = slide_shell("(b) 水平剖面：角度窗口与半径修正")
b = f.add_axes([-0.02, 0.01, 0.56, 0.97])
draw_section(b, fs=1.55, labels=False)
caption_column(f, [
    ("锚点间距 $18^\\circ$", GRAY),
    ("偏移窗口 $30^\\circ$（$\\pm15^\\circ$）", BLUE),
    ("相邻窗口重叠 $12^\\circ$", GREEN),
    ("", BLUE),
    ("$r'=r+\\Delta r$，上限 $8$ m", ORANGE),
    ("$=\\,v_{\\max}$ 直飞 $T$ 秒", ORANGE),
], y=0.80, dy=0.130)
f.savefig(OUT / "05b_primitive_section.png", facecolor=BG)
print("written:", OUT / "05b_primitive_section.png")
plt.close(f)

# ---- (c) primitive frame vs body frame
f = slide_shell("(c) 基元系与机体系：$R_{ij}$ 作用在哪里")
c = f.add_axes([-0.02, 0.01, 0.56, 0.97])
draw_rotation(c, fs=1.5, labels=False)
caption_column(f, [
    ("网络在基元系输出", PURPLE),
    ("终端速度与加速度", PURPLE),
    ("", PURPLE),
    ("$\\mathbf{v}_T=R_{ij}\\tanh(\\mathbf{y}_v)v_{\\max}$", ORANGE),
    ("经 $R_{ij}=R_z(\\varphi_i)R_y(-\\theta_j)$", INK),
    ("旋转回机体系", INK),
    ("", INK),
    ("位置不做旋转，", GREEN),
    ("由 $(r',\\theta',\\varphi')$ 直接算出", GREEN),
], x=0.585, y=0.84, dy=0.100)
f.savefig(OUT / "05c_frame_rotation.png", facecolor=BG)
print("written:", OUT / "05c_frame_rotation.png")
plt.close(f)
