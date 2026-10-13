# 07 可视化与展示

> 论文对应：Fig.7/8/10 的本地等效呈现（工程支撑 + 结果展示）｜ 一句话定位：把测量日志渲染成可看的视频与图表，并保证每个展示都能追溯到权重与飞行状态。

## 职责范围

三类输出：① 飞行回放视频与总览图（ROS2 链与原生链）；② 论文风格统计图（成功率—速度曲线、时延/安全性/平滑度表）；③ 演示编排（一键重跑展示链）。规则：回放不是新飞行；每个展示目录必须带 `metrics`（或等价来源）与 `render_manifest`，记录权重来源、checkpoint SHA256、飞行状态与"是否为回放"。

## 代码地图

| 路径 | 角色 | 说明 |
|---|---|---|
| [scripts/render_ros2_flight.py](../../scripts/render_ros2_flight.py) | ROS2 日志渲染器 | 从测量日志回放渲染视频/图片（最终展示使用） |
| [scripts/render_flight.py](../../scripts/render_flight.py) | 原生日志渲染器 | 原生链回放渲染 |
| [scripts/demo_flight.ps1](../../scripts/demo_flight.ps1) | 演示入口 | 统一查看与重跑入口（权重、速度、地图参数） |
| [scripts/run_final_showcase.ps1](../../scripts/run_final_showcase.ps1) | 最终展示链 | 审计权重的端到端展示重跑 |
| [scripts/run_showcase.ps1](../../scripts/run_showcase.ps1) | 早期展示链 | 官方 Simple 预训练部署阶段入口（历史，不替代自训练） |
| [scripts/make_paper_figures.py](../../scripts/make_paper_figures.py) | 统计图 | 由矩阵数据生成 Fig.7 成功率和 Table II 数据表 |
| [artifacts/ros2_showcase](../../artifacts/ros2_showcase) | 展示目录 | 每个 run 一个目录，含视频、图片与 `render_manifest.json` |
| [artifacts/paper_figures](../../artifacts/paper_figures) | 图表目录 | 图表文件与 `manifest.json` |
| [artifacts/demo_renders](../../artifacts/demo_renders)、[artifacts/showcase](../../artifacts/showcase) | 历史渲染 | 开发期渲染与官方权重演示（历史阶段） |

## 输入与输出

- 输入：`artifacts/ros2_flights/<run>/` 测量日志；权重与 run 名称（`--run`/演示参数）。
- 输出：`artifacts/ros2_showcase/<run>_final/`（`global_trajectory.mp4`、`global_overview.png`、`render_manifest.json`）、`artifacts/paper_figures/*`。

## 常用命令（项目根目录执行）

```powershell
Set-Location '<项目根目录>'

# 查看/重跑演示（含权重与地图参数）
./scripts/demo_flight.ps1

# 重新生成一次审计权重展示（需 Docker、镜像与 GPU）
./scripts/run_final_showcase.ps1 -Seed 0 -Speed 2 -MapSeed 3000 -Duration 60

# 重新生成论文图表
python scripts/make_paper_figures.py
```

## 证据与产物

| 产物 | 路径 | 说明 |
|---|---|---|
| 全局飞行视频 | [global_trajectory.mp4](../../artifacts/ros2_showcase/showcase_formal_main_v1_seed0_20260926_014921_final/global_trajectory.mp4) | 自训练 seed0 审计权重 |
| 全局轨迹图片 | [global_overview.png](../../artifacts/ros2_showcase/showcase_formal_main_v1_seed0_20260926_014921_final/global_overview.png) | 同上 |
| 渲染来源清单 | [render_manifest.json](../../artifacts/ros2_showcase/showcase_formal_main_v1_seed0_20260926_014921_final/render_manifest.json) | 记录权重 SHA256 与飞行状态 |
| 原始飞行指标 | `artifacts/ros2_flights/showcase_formal_main_v1_seed0_20260926_014921/metrics.json`（外部归档：完整飞行记录与逐架次证据见 report/06_migration） | 测量日志 |
| 论文图表 | [figure_7_success_vs_speed.png](../../artifacts/paper_figures/figure_7_success_vs_speed.png)、[table_ii_latency_split.md](../../artifacts/paper_figures/table_ii_latency_split.md) | 由矩阵数据生成 |
| 图表清单 | [manifest.json](../../artifacts/paper_figures/manifest.json) | 图表来源与生成信息 |

## 验证方法

- 渲染排练：`tests/test_paper_figures_rehearsal.py` 校验图表生成流程。
- 到达检查：新的展示目录必须能被 [05 可视化](../../report/05_visualization/README.md) 索引，且 `render_manifest.json` 中的权重 SHA256 与 `checkpoints/<run>/training_audit.json` 一致。

## 已知限制与论文差异

- 本地展示来自 Isaac 仿真闭环；论文的实机视频（Fig.9/10）没有本地等价物，本地回放不能称为实机飞行。
- 回放不产生新飞行证据；`test_paper_figures_rehearsal` 等排练产物不能进入正式结果。
- 官方 Simple 预训练演示（`run_showcase.ps1` 阶段）是历史记录，不替代自训练成果。

## 相关入口

- [模块总图](../../report/00_index/01_module_map.md) ｜ [05 可视化交付](../../report/05_visualization/README.md)
- [演示程序与权重飞行验证命令](../../report/05_visualization/01_演示程序与权重飞行验证命令.md)

