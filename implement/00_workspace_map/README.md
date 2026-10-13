# 00 工作区地图

> 论文对应：工程支撑，无直接论文对应 ｜ 一句话定位：运行根目录、目录职责和全部命令入口的一张表。

## 职责范围

项目的**运行根目录就是项目根目录**（即本仓库检出目录；旧机器上为 `<旧项目根>`）。代码没有被移动，因为脚本通过相对路径访问 external、configs、datasets、checkpoints 和 artifacts（多数脚本以 `Path(__file__).resolve().parents[1]` 解析根目录），Docker 把同一根目录挂载到 `/workspace`。`plan / implement / report` 是新增的管理与阅读入口，不承载可执行代码。

## 代码地图

| 路径 | 角色 | 说明 |
|---|---|---|
| `src/` | 算法与本地库 | `yopo_repro`（网络封装、代价、轨迹）、`yopo_sim`（仿真机体与轨迹缓冲）、`yopo_expert`、`agile_runtime`、`yopo_eval`、`yopo_dagger` |
| `scripts/` | 全部运行入口 | 数据、训练、审计、基准、基线、渲染和 PS1 流水线；清单见下表 |
| `configs/` | 固定配置 | `paper_aligned.json`（对齐 main 数值语义）、`reproduction_protocol.json`、`unified_quad.json`、`expert_variants.json` |
| `ros2_ws/src/` | ROS2 源码 | `yopo_runtime`、`yopo_interfaces`、`yopo_topotraj`、`yopo_expert_core`、`yopo_agile_core`、参考包 |
| `docker/`、`compose.yaml` | 训练容器 | `train-cu128-jammy` 等镜像定义；`--profile training` |
| `external/audit_sources/` | 固定上游源码 | `main`（正式主线）与 `YOPO-Simple`（官方 Simple 参考） |
| `datasets/` | 数据 | `isaac_full_v1`（100K/10K/10K）、`isaac_dagger_v1`（聚合微调） |
| `checkpoints/` | 权重与审计 | `formal_main_v1_seed{0,1,2}`、`dagger_main_v1_seed0` |
| `artifacts/` | 证据与展示 | 飞行原始记录、基准汇总、图表、演示视频与报告证据 |
| `benchmarks/` | 固定协议 | `protocol_v1`（任务、地图、准入与协议哈希） |
| `tests/` | 测试 | 核心算法、运行时与接口测试 |
| `reports/` | 兼容历史报告 | 详细历史来源文档；当前阅读从 `report/` 开始 |

## 常用命令（项目根目录执行）

```powershell
Set-Location '<项目根目录>'

# 训练与审计
./scripts/run_formal_training.ps1                 # 正式三种子训练（需容器与 GPU）
python scripts/train_scratch.py --help            # 单跑训练入口
python scripts/audit_training_run.py --run formal_main_v1_seed0 --seed 0
python scripts/check_training_integrity.py --help

# 数据
python scripts/validate_dataset.py --dataset datasets/isaac_full_v1
python scripts/stage_training_data.py --name isaac_full_v1

# ROS2 与仿真
python scripts/run_ros2_navigation.py             # ROS2 闭环飞行
python scripts/run_navigation.py                  # 原生 Isaac 链

# 验收与状态
python scripts/final_acceptance_audit.py
python scripts/audit_command_evidence.py --fail-on-missing
python scripts/make_status_overview.py

# 展示
./scripts/demo_flight.ps1
./scripts/run_final_showcase.ps1 -Seed 0 -Speed 2 -MapSeed 3000 -Duration 60
```

## 输入与输出

- 输入：根目录相对路径（`external/`、`configs/`、`datasets/`、`checkpoints/`、`artifacts/`）。
- 输出：训练写入 `checkpoints/<run>/`；飞行写入 `artifacts/ros2_flights/`；汇总写入 `artifacts/benchmark_summary/`、`artifacts/environment/`；展示写入 `artifacts/ros2_showcase/`、`artifacts/paper_figures/`。

## 证据与产物

| 产物 | 路径 | 说明 |
|---|---|---|
| 准入记录 | `benchmarks/protocol_v1/runtime_validation.json` | 运行协议与后端准入 |
| 机器状态 | `artifacts/environment/final_acceptance_audit.json`、`artifacts/environment/progress_brief.json` | 终审与进度简报 |
| 文档审计 | `artifacts/refactor_20261012/document_audit.json` | 报告链接与证据路径一致性检查 |

## 验证方法

- 语法：`python -m py_compile` 或 `compileall` 覆盖 `src/`、`scripts/`；PowerShell 入口用 `[scriptblock]::Create(...)` 解析。
- 链接：`python scripts/audit_command_evidence.py --fail-on-missing`；扩展覆盖 plan/implement/report 时见 [06 验证](../06_validation/README.md)。

## 已知限制

- 不要从 implement 子目录直接执行脚本；先把项目根设为当前目录。
- Windows 原生 Isaac 链与 Ubuntu 容器链共用同一根目录，路径大小写与分隔符差异由各脚本自行归一化。
- `artifacts/ros2_flights` 体积巨大（GB 级），不要递归扫描；用精确子目录名检查。

## 相关入口

- [中央模块总图](../../report/00_index/01_module_map.md)
- [implement 总入口](../README.md)
- [02 训练流水线](../02_training_pipeline/README.md)、[03 ROS2 运行时](../03_ros2_runtime/README.md)、[04 Isaac 仿真](../04_isaac_sim/README.md)

