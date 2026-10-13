# YOPO 汇报幻灯片

LaTeX Beamer 汇报稿，围绕两个角度组织：**前向推理**（候选轨迹如何生成）与**引导训练**（代价梯度如何进入网络）。
内容依据 [../README.md](../README.md)（2026-10-08 版）与 [论文 PDF（作者版）](../../../../artifacts/paper_sources/YOPO_author_version.pdf) 整理。

## 文件

```text
slides/
├── yopo_report.tex            # 主文件：导言区、样式、\input 各节
├── sections/
│   ├── 00_overview.tex        # 总览、文献信息、符号约定（5 页）
│   ├── 01_forward.tex         # 前向推理（19 页，含 3 页几何图）
│   ├── 02_training.tex        # 引导训练（18 页）
│   ├── 03_experiment.tex      # 实验数字（6 页）
│   └── 04_summary.tex         # 小结、易错点、待核对项（4 页）
└── figures/                   # 正文引用的全部图片（21 张）
```

其中 `24a`–`24c` 三张为球面修正量与坐标系转换的自绘说明图，由
[../tools/generate_offset_geometry.py](../tools/generate_offset_geometry.py) 生成：

```bash
cd YOPO/tools && python generate_offset_geometry.py
```

脚本同时输出两类文件：

| 输出 | 用途 |
| --- | --- |
| `assets/05_primitive_offset_geometry.png` | 三联合成图，供阅读与讲义 |
| `assets/05a|b|c_*.png` | 宽比例 + 大字号的单面板版，供投影 |

投影版在复制到 `figures/` 时改名为 `24a`–`24c`，
以免与原文 Fig.~5 的四张分图（`05a_simulated_scene` 等）重名混淆。

## 编译

需要 **XeLaTeX**（不能直接用 pdfLaTeX，中文依赖 `ctex`）：

```bash
cd slides
xelatex yopo_report.tex
xelatex yopo_report.tex      # 第二遍页码与总页数才正确
```

TeX Live 需包含 `ctex`、`beamer`、`booktabs`、`multirow`、`tikz`（含 `positioning`/`arrows.meta`/`calc`/`decorations.pathreplacing` 库）。
MiKTeX 首次编译会自动补装缺包。

**当前状态：已用 MiKTeX 25.12（winget 用户级安装）编译通过，共 50 页，无编译错误。**
剩余 1 处 6.3 pt 的 Overfull `\vbox` 出现在“还要预测终端速度与加速度”一页，
渲染后内容完整、无裁切，属排版告警而非内容缺失。

生成物 `yopo_report.pdf` 随目录保存；`.aux`/`.log`/`.nav` 等中间文件已在仓库根 `.gitignore` 中排除。

`\usepackage{ctex}` 使用 `fontset=auto`：Windows 下自动选用系统中文字体，Linux/Overleaf 下使用自带的 Fandol 字体，因此源码可以直接上传 Overleaf（编译器选 XeLaTeX）。

无本地 TeX 环境时，也可用 Docker 编译：

```bash
docker run --rm -v "$PWD":/w -w /w texlive/texlive:latest \
  xelatex -interaction=nonstopmode yopo_report.tex
```

## 内容约定

幻灯片沿用笔记的标注规则，用三种色块区分信息来源：

| 色块 | 含义 |
| --- | --- |
| 蓝色 `paperfinding` | 原文可查证的结论，已注明图/表/式编号 |
| 绿色 `teach` | 为便于理解构造的教学数字，**不是**论文实验数据 |
| 橙色 `reading` | 笔记整理者的推论，与原文陈述需区分 |

## 图片来源

| 文件前缀 | 来源 |
| --- | --- |
| `01_` – `10c_` | 原文配图，取自 MinerU 对 `YOPO_original.pdf` 的提取结果 |
| `20_` – `23_` | 笔记 [../assets/](../assets/) 中的原创教学示意图 |

图片已复制到本目录，不依赖 MinerU 输出目录；如需清理 PDF 提取的中间文件，本幻灯片不受影响。

## 已核对的实现细节

幻灯片正文以**笔记与原文**为准。以下几处是阅读原文时按现有配置可推出的数值，写法已在页面上注明来源：

- 锚点方位角 $\pm36^\circ/\pm18^\circ/0^\circ$、俯仰角 $\pm20^\circ/0^\circ$：
  由原文“在传感器可见范围内均匀采样”+ 5×3 网格 + 配置视场 90°×60° 推出；
- 偏移窗口 30°、基准半径 4 m：取自作者开源配置（论文正文只说明“略大于格子视场”）；
- 论文正文与公开代码在评分符号、候选筛选阈值、轨迹时域上存在差异，
  第 4 节“待核对清单”已列出，未在本稿中替任何一方下结论。
