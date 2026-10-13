# 新根重构与迁移计划（v2）

更新：2026-10-12 ｜ 对应 v1：[01_refactor_master_plan.md](01_refactor_master_plan.md) ｜ 执行记录：[report/06_migration/02_new_root_verification.md](../../report/06_migration/02_new_root_verification.md)

## 1. 需求回顾与设计对照

本次重构的目标是**可读性优先**的三层组织，并预设 GitHub 上传与 Ubuntu 22.04 接续：

| 需求 | 新根实现 |
|---|---|
| 分为 plan / implement / report 三大区 | 三大区在项目根并列；plan 管计划与决策、implement 管实施与代码工作区、report 管交付与展示 |
| 计划与管理项目：设计思路、代码框架、修改日志 | `plan/00_charter`（章程+v1/v2 计划）、`plan/99_change_log`（变更日志）、`plan/90_decisions`（决策记录，含提案参考文件） |
| 代码工作区：大模型接管实施与验证 | `implement/00–07` 模块地图 + `implement/workspace`（代码工作区视图）+ `implement/99_workspace_rules`（实施规范） |
| 报告展示区：markdown + HTML + 视频/动图 | `report/NN_*` 编号文件夹，内含详细报告；`report/00_index/03_project_map.html`（交互式项目全景）；`report/05_visualization/media/`（视频、图片、图表实体文件） |
| 标准编号-标题排序 | plan/report 的文件夹与文件均为 `NN_标题` 形式；入口 README 给出编号索引表 |
| GitHub + Ubuntu 22.04 迁移预设 | `.gitignore/.gitattributes` 就绪；`implement/workspace/bootstrap_links.{ps1,sh}` 生成跨平台工作区视图；数据/权重按 manifest 走 LFS/Release（见 `plan/06_github_migration`） |

## 2. 与 v1 主计划的关系（为什么不物理移动代码）

v1 主计划第 3 节明确：“本次不为了分类而移动现有运行代码……物理迁移必须另立决定，先加统一根目录解析函数和兼容包装”。本次在 v2 中复核了该约束，并补充实测证据：

1. **Docker 挂载不穿越 Windows junction**（本次实测：容器内看不到 junction 目标），因此“代码搬进 implement、根目录用链接指回去”会直接破坏 `docker compose` 的训练/ROS2 闭环。
2. 脚本以 `Path(__file__).resolve().parents[1]` 解析项目根，且 `benchmarks/protocol_v1/runtime_validation.json` 冻结了 20 个运行文件哈希——移动代码会同时破坏路径解析与证据链。
3. 结论：**代码真实文件保持项目根位置**；implement 通过“工作区视图（junction/符号链接）+ 模块地图 + 接管规范”实现可读性目标。视图不作为 git 内容，迁移后用 `bootstrap_links.sh` 重建。

决策记录：[DEC-20261012-01](../90_decisions/DEC-20261012-01_新根重构与工作区视图.md)。

## 3. 当前重构完成情况（对照 v1 六阶段）

| v1 阶段 | 状态 | 证据/说明 |
|---|---|---|
| 阶段0 冻结 | 已完成 | `artifacts/refactor_20261012/freeze_snapshot.json`：受保护文件哈希、三种子 best_policy 哈希实算复核（与 training_audit 全部一致）、数据/权重规模快照 |
| 阶段1 入口 | 已完成（v1 建层，v2 强化） | plan/implement/report 三层完备；v2 重排报告为编号文件夹并保留全部链接可用 |
| 阶段2 代码地图 | 已完成 | implement 00–07、99 共 9 份代码地图（入口/输入输出/命令/证据/限制） |
| 阶段3 报告整理 | 已完成（v2 定稿） | reports/ 20 份详细报告全部迁入 report 编号文件夹（01 状态 / 02 方法 / 03 训练 / 04 评测 / 05 可视化 / 90 历史 / 99 产物）；媒体实体文件落盘 report |
| 阶段4 Git 管理 | 部分完成 | 旧仓库主仓库已提交并推送源码与文档；新根本地 `git init` + 初始提交（见下）；大文件归档（LFS/Release）未上传 |
| 阶段5 迁移验证 | 部分完成 | 本机 Ubuntu 22.04 容器：GPU/ROS2 探针 + smoke 停止/恢复通过；独立 Ubuntu 主机迁移待执行 |
| 阶段6 验收 | 部分完成 | 文档链接审计、Python 编译、PowerShell 解析、核心测试、权重/协议哈希、代表视频均通过；独立主机迁移命令未跑 |

## 4. 新根目录设计（v2）

```text
YOPO_reproduction_new/
  plan/                     计划与管理（编号文件夹）
    00_charter/             章程、v1/v2 重构计划
    01_paper_protocol/      论文/源码/协议 + references/（原始笔记对话等）
    02_environment_ros2/    环境与迁移计划 + references/（isaac61_env 等）
    03_dataset_training/    数据与训练计划
    04_runtime_baselines/   运行时与基线计划
    05_benchmark_acceptance/基准与验收计划
    06_github_migration/    GitHub/LFS/Ubuntu 迁移计划与发布清单
    90_decisions/           决策记录 + references/（A/B 提案原文）
    99_change_log/          变更日志 + tools/（本次报告重排工具）
  implement/                实施区（大模型接管）
    00_workspace_map … 07_visualization、99_workspace_rules  模块地图
    workspace/              代码工作区视图（junction/符号链接 + 引导脚本）
  report/                   交付与展示区（编号文件夹）
    00_index/               阅读顺序、模块总图、执行手册、交互式项目全景（HTML）
    01_status/              当前进度简报、复现状态总览
    02_method/              论文对照、笔记对照、原文差异审计
    03_training/            从头训练进度、DAgger、专家对比
    04_evaluation/          官方vs自训练对照、权重实验、冻结口径、ROS2 迁移（MPPI 归档至 90_archive/mppi）
    05_visualization/       演示命令 + media/（视频、图片、图表实体文件）
    06_migration/           环境基线、新根验证记录
    90_archive/             历史阶段报告
    99_artifact_index/      产物索引 + 机器快照与中间证据
  src/ scripts/ configs/ docker/ ros2_ws/ tests/ external/ benchmarks/ vendor/ assets/
                            运行层（真实代码与资源，保持既有相对位置）
  datasets/ checkpoints/    数据与权重（本地 junction 引用原始归档；不入普通 Git）
  artifacts/                证据与演示（小体量复制，重目录 junction；不入普通 Git）
```

## 5. 内容处置表（转移 / 保留 / 修改 / 删除）

| 内容 | 处置 | 说明 |
|---|---|---|
| v1 的 plan/、implement/、report/ 文档 | **转移** | 整体复制进新根作为基础，并按编号规范增强（本表即增强产物之一） |
| reports/ 20 份详细报告 | **转移** | 迁入 report 编号文件夹并加序号前缀；`reports/README.md` 由 `report/README.md`+`00_index` 取代（不复制） |
| docs/proposals/（A/B 提案 4 件） | **转移** | → `plan/90_decisions/references/`，2026-10-13 再移入 `plan/90_decisions/archive_mppi/`（历史归档） |
| 项目外参考：笔记对话 conversation.txt | **转移** | → `plan/01_paper_protocol/references/`（SHA256 `b5d70813…` 校验一致） |
| 项目外参考：isaac61_env.md | **转移** | → `plan/02_environment_ros2/references/` |
| 运行代码 src/scripts/configs/docker/ros2_ws/src/tests/external/benchmarks/vendor/assets | **转移（复制）** | 保持相对位置不动；旧根保留为冻结镜像 |
| 小体量证据 artifacts/*（除 7 个重目录） | **转移（复制）** | 本地可直接解析文档链接；重目录见下行 |
| datasets 重数据、checkpoints 全量、artifacts 7 个重目录 | **保留原位** | 新根用 junction 本地引用；GitHub 走 LFS/Release；Ubuntu 按 manifest 恢复 |
| 旧根 YOPO_reproduction/ | **保留** | 冻结归档与运行兼容备份；旧仓库在切换前继续可用 |
| scripts/make_status_overview.py 默认输出 | **修改** | 默认改为 `report/01_status/02_复现状态总览.md` |
| scripts/audit_command_evidence.py 默认扫描范围 | **修改** | 默认改为 `report,plan` 并保留多目录/递归参数；文档审计命令见验收记录 |
| 任何实验数据 | **删除：无** | 本次未删除任何数据、权重或证据；仅不复制 `reports/README.md` 这一份被取代的索引 |

## 6. 后续路线（按优先级）

1. **新根验收复核**（本次执行）：链接审计 → 编译/语法 → 测试 → Docker GPU 探针 → smoke 停止/恢复 → 冻结快照；结果写入 `report/06_migration/02_new_root_verification.md`。
2. **GitHub 目标决策**：新仓库（推荐，保留旧仓库历史）或替换当前仓库 `main`；完成后推送新根、配置 LFS。
3. **大文件归档**：按 manifest 上传 datasets/checkpoints/代表视频（LFS 或 Release），记录 SHA256 与下载地址。
4. **独立 Ubuntu 22.04 主机迁移**：clone →（可选）`bash implement/workspace/bootstrap_links.sh` → 数据恢复校验 → GPU 探针 → smoke 停止/恢复 →（需要闭环时）Isaac 单独验证。
5. **旧根归档说明**：迁移验证通过后，在旧根 README 顶部标注“已迁移至新根”，旧仓库打 tag 冻结。
6. **实验线路**（2026-10-13 更新）：YOPO-only 活动矩阵 1,500 槽收官，MPPI 移出活动范围并归档；剩余研究限制为 DAgger 收益独立验证。
