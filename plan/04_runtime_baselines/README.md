# 04 运行时与基线计划

## YOPO

网络输出15个候选终端状态和评分，选择候选后生成五次多项式，再交给几何控制和PhysX。

## 专家

使用原版C++代价核心与显式标注的梯度优化/MMA重建，只用于离线比较，不作为正式训练标签。

## 外部基线

TopoTraj、Agile 已通过正式运行时准入并完成各自 300 槽。参考[17] MPPI 于 2026-10-13 经用户决定移出活动范围（全文/身份记录归档于 report/90_archive/mppi/，旧方案归档于 plan/90_decisions/archive_mppi/）；算法接入与 300 槽不再属于当前验收，活动范围声明见 benchmarks/protocol_v1/active_scope_yopo_only.json。
