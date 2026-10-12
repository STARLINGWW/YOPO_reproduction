# 05 可视化交付

更新：2026-10-12 ｜ 论文对应：Fig.7/8/10 的本地等效展示（回放，不是新飞行）

## 最终自训练成果（seed0，50 轮审计权重）

| 产物 | 路径 |
|---|---|
| 全局飞行视频 | [global_trajectory.mp4](../../artifacts/ros2_showcase/showcase_formal_main_v1_seed0_20260926_014921_final/global_trajectory.mp4) |
| 全局轨迹图片 | [global_overview.png](../../artifacts/ros2_showcase/showcase_formal_main_v1_seed0_20260926_014921_final/global_overview.png) |
| 渲染来源清单 | [render_manifest.json](../../artifacts/ros2_showcase/showcase_formal_main_v1_seed0_20260926_014921_final/render_manifest.json)（记录权重 SHA256 与飞行状态） |
| 原始飞行指标 | [metrics.json](../../artifacts/ros2_flights/showcase_formal_main_v1_seed0_20260926_014921/metrics.json) |

视频是测量 PhysX 日志的回放渲染。回放、接口探针不是新飞行；每个新演示都必须保存 `metrics.json` 和 `render_manifest.json`。

## 命令

```powershell
Set-Location 'D:\_AAA_CODE_ALL\Tech_reproduction\YOPO_reproduction'

./scripts/demo_flight.ps1                          # 演示入口（含查看与再运行）
./scripts/run_final_showcase.ps1 -Seed 0 -Speed 2 -MapSeed 3000 -Duration 60   # 重跑完整展示链
python scripts/render_ros2_flight.py --help        # 渲染器
python scripts/make_paper_figures.py               # 由矩阵数据生成论文图表
```

命令细节与权重来源见 [演示程序与权重飞行验证命令](../../reports/演示程序与权重飞行验证命令.md)。

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

