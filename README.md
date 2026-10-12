# YOPO 本地训练与 Isaac 仿真复现

更新：2026-10-08。**三种子从头训练、ROS2运行时准入、DAgger微调和自训练展示均已完成；正式基准已执行1,500/1,800，参考[17] MPPI的300个槽位尚未执行。** 当前终审为5 verified、1 documented_gap、1 pending，整体目标尚未全部验收。

项目根目录：`D:\_AAA_CODE_ALL\Tech_reproduction\YOPO_reproduction`。主线为Ubuntu22.04 Docker / ROS2 Humble + Windows原生Isaac Sim。当前训练与成果使用本地随机初始化训练权重；官方Simple预训练演示单独保留。

## 先阅读

**查看权重飞行效果请先打开[演示程序与命令合集](reports/演示程序与权重飞行验证命令.md)。**

项目结构重构入口：

1. [plan](plan/README.md)：计划、协议、决策、变更和GitHub/Ubuntu迁移。
2. [implement](implement/README.md)：代码实施区和根目录运行代码地图。
3. [report](report/README.md)：当前交付报告、方法说明、评测和可视化。
4. [复现模块总图](report/00_index/01_module_map.md)：把整个复现拆成模块，附论文章节反查和差异索引。

1. [当前进度简报](reports/当前进度简报.md)：已完成项、真实缺口和主要成果。
2. [复现状态总览](reports/复现状态总览.md)：由现有JSON产物生成的机器状态。
3. [报告索引](reports/README.md)：区分当前专题报告和历史阶段记录。
4. [执行手册](reports/执行手册.md)：现有训练、恢复、审计和展示入口。
5. [笔记与本地实现对照](reports/YOPO笔记与本地复现逐项对照_2026-10-08.md)：训练数据流、评分符号、候选筛选等差异。

## 可直接查看的最终自训练成果

- [全局飞行视频](artifacts/ros2_showcase/showcase_formal_main_v1_seed0_20260926_014921_final/global_trajectory.mp4)
- [全局轨迹图片](artifacts/ros2_showcase/showcase_formal_main_v1_seed0_20260926_014921_final/global_overview.png)
- [来源清单](artifacts/ros2_showcase/showcase_formal_main_v1_seed0_20260926_014921_final/render_manifest.json)
- [正式基准汇总](artifacts/benchmark_summary/summary.json)
- [成功率与速度图](artifacts/paper_figures/figure_7_success_vs_speed.png)
- [官方与本地权重36架次比较](reports/权重批量对照实验.md)

## 目录与模型

| 目录 | 内容 |
|---|---|
| `external/audit_sources/main` | 正式主线的固定版源码与轨迹配置 |
| `external/audit_sources/YOPO-Simple` | 官方Simple参考源码及预训练权重 |
| `src`、`scripts`、`ros2_ws/src` | 算法、训练、仿真、接口与评测实现 |
| `datasets/isaac_full_v1` | 100K训练、10K验证、10K离线测试 |
| `checkpoints/formal_main_v1_seed{0,1,2}` | 三份正式模型；部署使用各自`best_policy.pth` |
| `datasets/isaac_dagger_v1`、`checkpoints/dagger_main_v1_seed0` | 独立聚合数据与微调权重 |
| `benchmarks/protocol_v1` | 固定任务、地图及已通过准入的记录 |
| `artifacts/ros2_flights` | 正式与开发飞行原始记录，按scope区分 |
| `artifacts/ros2_showcase`、`artifacts/paper_figures` | 自训练展示和统计图表 |
| `plan` | 项目计划、决策、变更与迁移管理 |
| `implement` | 代码、训练、运行时和验证的导航入口 |
| `report` | 交付报告和可视化展示入口 |
| `reports` | 兼容路径、详细历史报告和当前来源文档 |

## 运行入口

重新生成一次审计权重展示（先确认Docker Linux engine、镜像和GPU可用）：

```powershell
Set-Location 'D:\_AAA_CODE_ALL\Tech_reproduction\YOPO_reproduction'
./scripts/run_final_showcase.ps1 -Seed 0 -Speed 2 -MapSeed 3000 -Duration 60
```

只刷新报告呈现，不运行训练或飞行：

```powershell
python scripts/make_status_overview.py
python scripts/audit_command_evidence.py --fail-on-missing
```

旧的[官方权重演示](artifacts/showcase/forest_seed7_v3/yopo_global_flight.mp4)由`run_showcase.ps1`运行，属于已完成的预训练部署阶段。它不替代自训练成果。

参考[17]全文已具备；A为补齐实现与300次实验，B为明确缩小验收范围，C为保留现状。详见[MPPI说明](reports/MPPI参考17身份与可得性.md)。本次报告整理没有应用A/B，也没有改变实验协议或验收判据。
