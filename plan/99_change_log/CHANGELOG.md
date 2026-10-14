# 计划与管理变更日志

## 2026-10-14 项目全景页转 Markdown + 论文 Fig.7 口径的速度对比图

- 项目全景页由交互式 HTML 改为 Markdown：移除 `report/00_index/03_project_map.html` 与其两张截图，新增 `report/00_index/03_project_map.md`（12 模块状态表 + 关键入口 + 活动矩阵 1,500/1,500 与结果构成），并同步更新 README、report/README、report/00_index/README、module_map、重构计划与迁移记录中的引用。
- 新增论文 Fig.7 口径图：稀疏（1/30）/稠密（1/20）双面板的**成功率**与**碰撞率** vs 2–10 m/s（ROS2 冻结矩阵：自训练 YOPO 三种子合并、TopoTraj、Agile），由 `scripts/make_benchmark_speed_figures.py` 从冻结汇总生成，附逐格数值表。
- 自训练 vs 官方权重补测（原生 main 链 A/B，矩阵之外）：新增稀疏 8/10 m/s 与稠密 2–10 m/s 共 42 架次（`main_official` / `main_local`，各 3 场景 × 速度、120 s 仿真上限），补全后再绘制成功/碰撞率 2×2 同场景对比图；官方权重只在原生链可比（冻结 ROS2 规划器拒绝非 scratch 来源）。

## 2026-10-13 YOPO-only 范围冻结、MPPI 归档与文档归一化

- 活动范围冻结：新增 `benchmarks/protocol_v1/active_scope_yopo_only.json`（五模型 × 300 = 1,500）；`scripts/aggregate_benchmarks.py` 默认按活动范围汇总（`--superset` 复算 1800 口径）；`scripts/final_acceptance_audit.py`、`scripts/make_status_overview.py`、`scripts/create_benchmark_protocol.py` 与三个基准测试同步更新。
- 派生验收重生成：`artifacts/benchmark_summary/summary.json`（`outcome_coverage_complete`，1500/1500）、`artifacts/environment/final_acceptance_audit.json`（6 verified、all_verified=true）、`artifacts/environment/status_overview.json` 与 `report/01_status/02_复现状态总览.md`。
- 历史归档：新增 `benchmarks/archive/README.md` 与 `benchmarks/archive/protocol_v1_1800/`（1800 调度快照、超集汇总、冻结前终审、`mppi_reference17_episodes.json`）；MPPI 调查记录移入 `report/90_archive/mppi/`，A/B 方案移入 `plan/90_decisions/archive_mppi/`（标签 `historical / not_used_by_active_yopo_only_release`）。
- 决策记录：新增 `plan/90_decisions/DEC-20261013-01_MPPI移出活动范围与YOPO-only归档.md`；90_decisions README 改为“已决”清单。
- 证据字节锚定：`.gitattributes` 对 `benchmarks/protocol_v1/{protocol.json,maps/*.json,runtime_validation.json}`、`configs/unified_quad.json`、`configs/topotraj/isaac_development.yaml`、`datasets/**`、`artifacts/**`、`checkpoints/**`、`external/audit_sources/**` 加 `-text`，并重加 protocol/maps/runtime_validation 的原文，保证 clone 后 sha256 与记录一致（`d2fd3052…` / `25649f9d…`）。
- 文档归一化（移植性）：清除活动文档中的本机绝对路径（README、benchmarks/README、plan/**、report/**、执行手册、project_map.html 等）；历史记录中的机器路径替换为 `<旧项目根>`/`<本机Isaac环境>` 占位符并标注（90_archive、machine_audit.json、isaac_depth_initial_failure.txt）。
- 报告语义同步：终审口径改为 6 verified / 0 documented_gap / 0 pending；活动矩阵 1,500/1,500；MPPI 不再作为当前待办（module_map、01_status、02_method、03_training、04_evaluation、project_map.html 等）。
- 标准文档审计（report/plan/benchmarks/implement + 根文档）：73 份、0 缺失链接、0 缺失路径、0 不可解析 JSON。
- 准入勘误（透明记录）：`scripts/run_benchmark_matrix.py` 仅把机器解释器默认值改为 `YOPO_ISAAC_PYTHON` 环境变量（容器内启动命令不变），并在 `benchmarks/protocol_v1/runtime_validation.json` 增加 `runtime_files_amendment`（含旧/新 sha256 与原因）；其余 19 个冻结运行文件字节未变。既有飞行证据与准入阶段结果不受影响；后续任何再次修改运行时文件都会使准入失效。
- 发布内容精选：`checkpoints/formal_main_v1_seed{0,1,2}` 与 `dagger_main_v1_seed0` 由 junction 实体化为精简副本（best_policy + 审计/结果 JSON，5+5+5+3 个文件）；`datasets/**` 保留清单类 JSON 与 smoke 子集；`artifacts/**` 保留 summary、环境审计、图表、专家对照、agile 清单与最终展示媒体。
- 证据归一化：`report/05_visualization/media` 三份渲染/指标 JSON 与 `assets/cf21b/payloads/base.usda` 的构建机路径改为项目相对路径或占位符（base.usda 仅 `doc` 元数据字符串变化）；`report/99_artifact_index/implementation_sha256.json` 按发布字节重算（5 个条目变化，含 run_showcase.ps1）。
- 发布清理：移除 `vendor/probe_deps/bin/{markdown-it,pygmentize}.exe`（pip 生成的启动器 stub，内嵌构建机路径且无脚本引用；旧根与 git 历史保留）；4 份 `document_audit*.json` 的机器路径归一化为占位符并重跑全量审计（73 份、0 缺失）。
- 未修改：固定超集协议字节、既有飞行与训练证据；未重跑矩阵或新增飞行。
- GitHub 发布执行：旧 main 归档 tag `archive/pre-yopo-only-20261013`（→ `7321edf`）；`main` 以 force-with-lease 替换为发布提交链 `2037820 → e718a77 → 243a1f8`；LFS 147 对象、约 656 MB 推送。干净 clone 全量验证通过：grep 0、75 份文档审计 0 缺失、compileall、pytest 87、终审 6/6、权重哈希一致、Docker GPU 探针与 smoke 停止/恢复通过；详见 report/06_migration/03_github_release_verification.md。
- README 首屏对照资产：新增 report/05_visualization/media/official_vs_selftrained/（三场景同场景轨迹大图 + 官方/自训练同步动画 + 深度帧静态对照），由 scripts/make_official_vs_selftrained_figure.py 从 weights A/B 36 架次原始日志生成；README 顶部加入“图文速览”与离线/闭环对照表。
- 对照可视化改版：三格轨迹面板改为“双方都到达”的同类场景直接对照；GIF 合成为「上：俯视轨迹 / 下：机载深度相机」双面板（同一仿真时间同步，场景 5001 · 4 m/s）。官方到达后深度采集结束，该侧面板以压暗蒙层 + “已到达·深度采集结束”标注呈现（避免误读为卡顿），时间窗收窄至最晚到达后约 2.5 s。
- 本地专用内容整理：`vendor/`（探查依赖）与 Fast-Planner 的过期编译产物（4 个 build 目录）移入被忽略的 `local_only/`，从上传中移除但完整保留在本地（使用移动而非删除）；README 目录总表补充各目录与根文件含义。
- 到达口径可视化：轨迹图例与 GIF 末帧改为「入圈（1 m）→ 稳定达标」双时刻；闭环对照表增加“稳定达标中位”列；README 新增「折返成因」小节（终端 1 m 切换 + 低增益保持 + 高速余量导致过冲回稳，非判据差异、非绕行）并嵌入 04_terminal_phase.png 终端阶段标注图；评测报告同步补充机制与定量锚点。
- README 规范化：项目名统一为「YOPO 复现工程 · YOPO Reproduction」；补论文/官方主页/官方仓库链接与徽章、快速开始、复现结果与验证、与官方主项目关系、引用（官方 BibTeX）、相关项目（官方 YOPO/YOPO-Sim/YOPO-Rally 与社区 YOPO-ROS2）、许可致谢与变更入口；修正闭环对照表重复表头。
- 新增「复现总流程图」：scripts/make_pipeline_flowchart.py 生成 report/00_index/04_pipeline_flowchart.png（在线推理链 / 本地模块映射 / 训练与验收证据链三带合一），README 与模块总图同步引用。
- 阅读笔记随复现分发：report/02_method/reading_note/（精读笔记 README、自绘 assets、工具与 50 页 Beamer 汇报及 TeX 源码；引用路径已改为仓库内相对链接），README 新增「阅读笔记」小节并与方法对照互联。
- 复现总流程图视觉改版：六个推理卡等宽等距、闭环回路改为带白色标牌的正交走线（顶部跨越、垂直箭头指回深度图）、本地实现四条映射改为共用一条车道的正交折线（消除交叉与文字遮挡）、统一圆角卡片 + 柔和阴影 + 标题/正文分层字体，重新生成 report/00_index/04_pipeline_flowchart.png（README 与模块总图引用路径不变）。
- README 新增「ToDo（后续计划）」：标记 Windows（Docker Desktop + Isaac Sim 6.1）全链路复现已完成，规划 Ubuntu 22.04 环境复验、原生训练与原生部署（闭环仿真/实机）及迁移报告回填。

## 2026-10-12 新根重构（v2）

- 建立 `YOPO_reproduction_new/` 新根：plan / implement / report 三大区 + 运行层（代码保持既有相对位置）。
- report 改为编号文件夹：22 份详细报告迁入 01_status / 02_method / 03_training / 04_evaluation / 05_visualization / 90_archive / 99_artifact_index / 00_index，并加序号前缀。
- 报告媒体实体落盘：`report/05_visualization/media/`（视频、图片、Table I/II、渲染清单）、`report/00_index/03_project_map.html`（交互式项目全景 + 截图）。
- `docs/proposals/` → `plan/90_decisions/references/`；项目外参考 conversation.txt、isaac61_env.md 随迁为 plan references（含 SHA256 校验）。
- implement 增加 `workspace/` 代码工作区视图与 `bootstrap_links.{ps1,sh}`；依据见 DEC-20261012-01（Docker 挂载不穿越 junction）。
- 链接迁移：770 处引用 + 16 处绝对路径重写为相对路径；全库文档审计 0 缺失（见 report/06_migration/02_new_root_verification.md）。
- 修改两个脚本默认值：make_status_overview.py 默认输出报告页、audit_command_evidence.py 默认扫描 report/plan。
- 未删除任何数据、权重或实验证据；旧根保留为冻结归档。

## 2026-10-12

- 建立 plan / implement / report 三个项目入口。
- 保留根目录运行路径，避免移动代码破坏 ROOT=Path(...).parents[1] 和容器 /workspace。
- 增加GitHub、LFS和Ubuntu 22.04迁移计划。
- 把当前、历史、算法、训练、评测和展示报告分层索引。
- 新增 report/00_index/01_module_map.md：复现模块总图（5 阶段 × 12 模块）与论文章节反查、差异索引。
- 新增 report/02_method/01_paper_to_code.md：论文 II-A/II-B/III 与本地代码的逐项对照。
- 扩写 implement 各模块 README 为代码地图（入口、输入输出、证据、限制）与 00/99 工作区规范。
- 填充 report 分类页（01 状态、03 训练、04 评测、05 可视化、06 迁移、90 历史、99 产物索引）。
- `scripts/audit_command_evidence.py` 增加向后兼容的 `--recursive` 与 `--extra-files`（`--reports` 支持多目录）；默认行为不变。
- 文档审计扩展到 plan/implement/report/根文档：59 份、0 缺失链接、0 缺失路径、0 不可解析 JSON → artifacts/refactor_20261012/document_audit_all.json。
- 运行 scripts/check_training_integrity.py 生成 artifacts/environment/seed_training_integrity_v2.json（三种子指标流检查通过，无异常）。
- 清理 12:18 误建的空目录 YOPO_reproduction/YOPO_reproduction（0 文件）。
- 独立复跑复核：`python -m compileall -q src scripts` 通过；59 份文档扩展审计 0 缺失链接、0 缺失路径；终审 JSON 与提交内容一一对应。
- 未修改固定协议、审计权重和正式实验结果；验收脚本仅做上述向后兼容扩展。
- 新增 report/04_evaluation/01_official_vs_selftrained.md：官方权重 vs 自训练权重总对照（离线 10k + 闭环 36 架次 + 两阶段展示）。
- 新增 report/06_migration/01_local_environment.md：本机 Docker/环境基线、启动故障修复与 2026-10-12 容器验证记录。
- 验证通过：GPU/ROS2 探针、smoke 训练停止/恢复（`checkpoints/migration_smoke_v1`，status=complete，不进入正式矩阵）。
- 新增证据 artifacts/refactor_20261012/{docker_version.json,docker_images.jsonl,docker_info.json,train_env_gpu_probe.log,migration_smoke_*.log}。
- 新增 scripts/refactor_freeze_snapshot.py 与 artifacts/refactor_20261012/freeze_snapshot.json（阶段0 冻结）：受保护文件哈希、三种子 best_policy 哈希实算复核（全部与 training_audit 一致）、数据与 checkpoint 规模快照。
