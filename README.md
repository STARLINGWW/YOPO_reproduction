# YOPO 复现项目（重构新根 v2）

更新：2026-10-13 ｜ 本目录是重构后的主项目：**plan / implement / report 三层组织 + 运行层**。旧项目 `../`（YOPO_reproduction）保留为冻结归档，重构说明见 [plan/00_charter/02_new_root_refactor_plan.md](plan/00_charter/02_new_root_refactor_plan.md)。

当前状态：三种子训练、ROS2 准入、DAgger 微调、最终展示与 YOPO-only 活动矩阵（1,500/1,500，五模型 × 300）全部完成；终审 **6 verified、all_verified=true**。参考[17] MPPI 按用户决定（2026-10-13）移出活动范围并归档，见 [benchmarks/archive](benchmarks/archive/README.md) 与 [report/90_archive/mppi](report/90_archive/mppi/README.md)，不再计入当前验收。

## 三层入口

| 区 | 入口 | 内容 |
|---|---|---|
| plan | [plan/README.md](plan/README.md) | 章程与 v1/v2 重构计划、论文协议、环境、数据训练、基线、验收、GitHub/Ubuntu 迁移、决策与变更日志 |
| implement | [implement/README.md](implement/README.md) | 00–07、99 共 9 份代码地图；[implement/workspace](implement/workspace/README.md) 为代码工作区视图（junction/符号链接） |
| report | [report/README.md](report/README.md) | 编号报告文件夹：状态、方法、训练、评测、可视化（含媒体实体文件）、迁移、历史、产物索引 |

## 先阅读

1. [复现模块总图](report/00_index/01_module_map.md)：5 阶段 × 12 模块，“论文 → 实现 → 证据 → 报告”一张图走通。
2. [执行手册](report/00_index/02_执行手册.md)：现有训练、恢复、审计和展示命令。
3. [当前进度简报](report/01_status/01_当前进度简报.md)、[复现状态总览](report/01_status/02_复现状态总览.md)：完成项与真实缺口。
4. [官方权重 vs 自训练权重对照](report/04_evaluation/01_official_vs_selftrained.md)：离线 1 万样本 + 闭环 36 架次。
5. [交互式项目全景（HTML）](report/00_index/03_project_map.html)：12 模块可点选，附活动矩阵 1,500 槽分布图（YOPO-only；MPPI 已移出并归档）。

## 可直接查看的成果

- [全局飞行视频](report/05_visualization/media/global_trajectory.mp4) ｜ [全局轨迹图片](report/05_visualization/media/global_overview.png) ｜ [渲染来源清单](report/05_visualization/media/render_manifest.json)
- [官方预训练演示视频](report/05_visualization/media/official_pretrained_flight.mp4)（早期阶段，单独保留）
- [论文图表](report/05_visualization/media/paper_figures)：Fig.7 成功率—速度曲线、Table I/II
- 全部逐架次指标与哈希索引：[report/99_artifact_index](report/99_artifact_index/README.md)

## 运行入口（从本目录执行）

```powershell
cd <项目根目录>   # 克隆到本机后的项目根目录，例如 ~/YOPO_reproduction

# 环境探针（Docker Desktop Linux 容器，Ubuntu 22.04 + ROS2 Humble + GPU）
docker compose --profile training run --rm train python3 scripts/ros2/verify_environment.py --gpu

# smoke 训练：停止 / 恢复 / 完成
docker compose --profile training run --rm train python3 scripts/train_scratch.py --dataset /workspace/datasets/smoke_v1 --run migration_smoke_newroot --seed 0 --epochs 1 --batch-size 16 --stop-after-steps 20
docker compose --profile training run --rm train python3 scripts/train_scratch.py --dataset /workspace/datasets/smoke_v1 --run migration_smoke_newroot --seed 0 --epochs 1 --batch-size 16 --resume

# 文档/证据一致性审计（新根标准命令）
python scripts/audit_command_evidence.py --reports "report,plan,benchmarks,implement/00_workspace_map,implement/01_core_algorithm,implement/02_training_pipeline,implement/03_ros2_runtime,implement/04_isaac_sim,implement/05_baselines,implement/06_validation,implement/07_visualization,implement/99_workspace_rules" --recursive --extra-files "README.md,MIGRATION_UBUNTU22.md,CONTRIBUTING.md,AGENTS.md" --fail-on-missing

# 审计展示重跑（需要 Docker Linux engine、镜像和 GPU）
./scripts/run_final_showcase.ps1 -Seed 0 -Speed 2 -MapSeed 3000 -Duration 60
```

## 迁移（GitHub + Ubuntu 22.04）

- 工作区视图重建（clone 后可选）：Windows `./implement/workspace/bootstrap_links.ps1`；Ubuntu `bash implement/workspace/bootstrap_links.sh`。
- Ubuntu 接续步骤：[MIGRATION_UBUNTU22.md](MIGRATION_UBUNTU22.md)；本机容器验证记录：[report/06_migration](report/06_migration/README.md)。
- Git/LFS 与大文件规则：[plan/06_github_migration/README.md](plan/06_github_migration/README.md)；发布清单：[plan/06_github_migration/01_release_checklist.md](plan/06_github_migration/01_release_checklist.md)。

## 目录总表

| 目录 | 内容 |
|---|---|
| `plan/` | 计划与管理（编号文件夹，含决策记录与参考文件） |
| `implement/` | 实施区：模块地图 + `workspace/` 代码工作区视图 |
| `report/` | 交付展示区（编号文件夹，含 HTML 与视频/图片/图表实体文件） |
| `src/`、`scripts/`、`configs/` | 算法库、运行入口与配置（真实代码，位于项目根以保证运行兼容） |
| `docker/`、`compose.yaml` | Ubuntu 22.04 jammy 容器（训练 / ROS2 / 基线 / 专家） |
| `ros2_ws/src/` | ROS2 源码（yopo_runtime、interfaces、topotraj、expert、agile、参考包） |
| `external/` | 固定上游源码（audit_sources：main、YOPO-Simple 等） |
| `benchmarks/` | 冻结协议与准入记录 |
| `datasets/`、`checkpoints/` | 数据与权重（本地引用归档，不入普通 Git；发布走 LFS/Release） |
| `artifacts/` | 证据与演示（小体量复制；重目录本地引用归档） |
