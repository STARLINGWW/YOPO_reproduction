# 05 可视化交付

更新：2026-10-12 ｜ 论文对应：Fig.7/8/10 的本地等效展示（回放，不是新飞行）

## 本目录媒体实体文件（media/）

| 文件 | 说明 |
|---|---|
| [global_trajectory.mp4](media/global_trajectory.mp4) | 自训练 seed0 最终展示视频（50 轮审计权重） |
| [global_overview.png](media/global_overview.png) | 全局轨迹总览图 |
| [render_manifest.json](media/render_manifest.json) | 渲染来源清单（权重 SHA256、飞行状态） |
| [showcase_metrics.json](media/showcase_metrics.json) | 展示飞行原始指标（成功、RMSE 0.116 m、净空 1.188 m） |
| [official_pretrained_flight.mp4](media/official_pretrained_flight.mp4) | 官方 Simple 预训练演示（早期阶段，单独保留） |
| [media/official_vs_selftrained](media/official_vs_selftrained) | README 首屏对照：同场景轨迹大图 + 「轨迹/机载深度」同步动画 + 深度帧静态对照 + 终端阶段标注（折返成因） |
| [media/paper_figures](media/paper_figures) | Fig.7 曲线、Table I/II 汇总（png/pdf/csv/md） |

## 最终自训练成果（seed0，50 轮审计权重）

| 产物 | 路径 |
|---|---|
| 全局飞行视频 | [global_trajectory.mp4](../../artifacts/ros2_showcase/showcase_formal_main_v1_seed0_20260926_014921_final/global_trajectory.mp4) |
| 全局轨迹图片 | [global_overview.png](../../artifacts/ros2_showcase/showcase_formal_main_v1_seed0_20260926_014921_final/global_overview.png) |
| 渲染来源清单 | [render_manifest.json](../../artifacts/ros2_showcase/showcase_formal_main_v1_seed0_20260926_014921_final/render_manifest.json)（记录权重 SHA256 与飞行状态） |
| 原始飞行指标 | `artifacts/ros2_flights/showcase_formal_main_v1_seed0_20260926_014921/metrics.json`（外部归档：完整飞行记录与逐架次证据见 report/06_migration） |

视频是测量 PhysX 日志的回放渲染。回放、接口探针不是新飞行；每个新演示都必须保存 `metrics.json` 和 `render_manifest.json`。

## 命令

```powershell
cd <项目根目录>   # 克隆后的项目根目录

./scripts/demo_flight.ps1                          # 演示入口（含查看与再运行）
./scripts/run_final_showcase.ps1 -Seed 0 -Speed 2 -MapSeed 3000 -Duration 60   # 重跑完整展示链
python scripts/render_ros2_flight.py --help        # 渲染器
python scripts/make_paper_figures.py               # 由矩阵数据生成论文图表
```

命令细节与权重来源见 [演示程序与权重飞行验证命令](01_演示程序与权重飞行验证命令.md)。

## 论文图表

- [figure_7_success_vs_speed.png](../../artifacts/paper_figures/figure_7_success_vs_speed.png)
- [table_i_expert_vs_network.md](../../artifacts/paper_figures/table_i_expert_vs_network.md)
- [table_ii_latency_split.md](../../artifacts/paper_figures/table_ii_latency_split.md)
- [manifest.json](../../artifacts/paper_figures/manifest.json)：图表清单与来源。

## 边界

- 展示来自自训练权重；官方 Simple 预训练演示单独保留在 [artifacts/showcase](../../artifacts/showcase)，不替代自训练成果。
- 本地为 Isaac 仿真闭环展示，不是论文实机飞行（差异 D11）。

## 相关入口

- [模块总图](../00_index/01_module_map.md) ｜ [04 评测](../04_evaluation/README.md)
- [implement/07 可视化](../../implement/07_visualization/README.md)：渲染器与脚本代码地图。

