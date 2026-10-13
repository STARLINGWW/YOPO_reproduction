# 00 项目章程

## 目标

在本地完成 YOPO 的数据生成、随机初始化训练、ROS2/Isaac闭环、专家和基线对照，并保留可追溯的模型、日志、指标和可视化成果。

## 范围

- Ubuntu 22.04、ROS2 Humble、Docker训练环境。
- Windows Isaac Sim作为传感器、PhysX和展示环境。
- 本地生成的程序化森林数据。
- 三种正式随机初始化YOPO权重。
- TopoTraj、Agile 的协议化比较（参考[17] MPPI 于 2026-10-13 移出活动范围并归档）。
- DAgger访问数据聚合与独立微调。

## 当前完成定义

当前已完成三种子训练、准入、专家比较、DAgger微调、最终自训练展示，以及 YOPO-only 活动矩阵 1,500/1,500 与 6 项机械验收（all_verified=true）。参考[17] MPPI 已移出活动范围并归档，不再作为交付缺口；剩余研究限制（DAgger 闭环收益独立验证、实机未复现）见 report/01_status。
