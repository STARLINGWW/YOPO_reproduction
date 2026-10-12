# 04 评测交付

更新：2026-10-12 ｜ 论文对应：III-A 训练策略验证（Table I）、III-B 仿真对比（Table II、Fig.7）

## 正式矩阵（1500 / 1800）

协议：[benchmarks/protocol_v1](../../benchmarks/protocol_v1)（协议哈希 `d2fd3052…`，记录于 [summary.json](../../artifacts/benchmark_summary/summary.json)）。矩阵为 6 个模型 × 2 密度 × 5 速度 × 30 架次 = 1800；当前完成 1500，缺口 300 全部是参考[17] MPPI（未实现）。

| 模型 | 完成 | 成功 | 碰撞 | 超时 |
|---|---|---|---|---|
| YOPO seed0 | 300/300 | 184 | 42 | 74 |
| YOPO seed1 | 300/300 | 163 | 50 | 87 |
| YOPO seed2 | 300/300 | 174 | 36 | 90 |
| TopoTraj | 300/300 | 71 | 227 | 2 |
| Agile Autonomy | 300/300 | 30 | 269 | 1 |
| 参考[17] MPPI | 0/300 | — | — | — |
| 合计 | 1500/1800 | 622 | 624 | 254 |

统计口径：失败保留在成功率分母中，缺失架次记为未知；Wilson 区间只描述已完成架次。详见 [summary.json](../../artifacts/benchmark_summary/summary.json) 的 `statistics_note`。

## 专家对照（论文 Table I）

- 独立离线测试集、审计权重、全量 10,000 样本：三种子 + 随机初始化。
- 证据：[network_comparison_trained_seed0.json](../../artifacts/expert/network_comparison_trained_seed0.json)、seed1、seed2 与 [random_initial](../../artifacts/expert/network_comparison_random_initial.json)。
- 汇总表：[table_i_expert_vs_network.md](../../artifacts/paper_figures/table_i_expert_vs_network.md)。

## 时延与图表（论文 Table II、Fig.7）

- [figure_7_success_vs_speed.png](../../artifacts/paper_figures/figure_7_success_vs_speed.png)：成功率—速度曲线（由矩阵数据生成）。
- [table_ii_latency_split.md](../../artifacts/paper_figures/table_ii_latency_split.md)：规划链时延拆分。
- [table_ii_latency_safety_smoothness.md](../../artifacts/paper_figures/table_ii_latency_safety_smoothness.md)：时延、安全性与平滑度汇总。
- 生成入口：`scripts/make_paper_figures.py`；清单：[manifest.json](../../artifacts/paper_figures/manifest.json)。

## 权重与运行栈对照

- 官方权重 vs 自训练权重总对照（离线 10k + 闭环 36 架次 + 两阶段展示）：[01_official_vs_selftrained.md](01_official_vs_selftrained.md)。
- 36 架次官方/本地权重批量对照（30 成功 / 4 超时 / 2 碰撞，样本量限制不可外推总体排名）：[权重批量对照实验](02_权重批量对照实验.md)，数据在 [artifacts/weights_ab_demo](../../artifacts/weights_ab_demo)。
- 运行栈准入（agile/topotraj/yopo 三后端）：[runtime_validation.json](../../benchmarks/protocol_v1/runtime_validation.json)。

## 详细报告

- [复现状态总览](../01_status/02_复现状态总览.md)：由权威 JSON 生成的机器状态。
- [基准运行配置冻结](04_基准运行配置冻结.md)：实际 passed 准入与历史声明的区别。
- [ROS2基线迁移记录](06_ROS2基线迁移记录.md)：TopoTraj/Agile 实际准入、CUDA 与闭环结果。
- [权重对比演示实验](03_权重对比演示实验.md)：早期单场景对照，不能外推。

## 相关入口

- [模块总图](../00_index/01_module_map.md) ｜ [01 当前状态](../01_status/README.md) ｜ [05 可视化](../05_visualization/README.md)
- [implement/05 基线](../../implement/05_baselines/README.md)、[implement/06 验证](../../implement/06_validation/README.md)

