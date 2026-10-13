# 固定任务与正式基准结果

更新：2026-10-13。固定任务和运行时文件已冻结，`protocol_v1/runtime_validation.json`已存在且status=passed，准入后端为YOPO、TopoTraj、Agile。**YOPO-only 活动矩阵已收官：1,500/1,500（五模型 × 300）**；参考[17] MPPI 按用户决定移出活动范围，1800 槽超集协议与旧汇总保留为历史锚点（`historical_protocol_v1`，见 [archive/README.md](archive/README.md)）。

## 任务与覆盖

20张独立地图、两档密度（1/30、1/20）、五档速度（2/4/6/8/10m/s）、每条件30次，每模型300次。活动范围为五模型（三份自训练 YOPO + TopoTraj + Agile）共 1,500 个槽位，已全部执行；1800 槽超集协议保留为历史锚点（活动范围声明见 [protocol_v1/active_scope_yopo_only.json](protocol_v1/active_scope_yopo_only.json)）。每条件前10次是论文规模子集，不能与all30重复相加。

| 模型 | 成功 | 碰撞 | 超时 | 已执行/计划 |
|---|---:|---:|---:|---:|
| yopo_seed0 | 184 | 42 | 74 | 300/300 |
| yopo_seed1 | 163 | 50 | 87 | 300/300 |
| yopo_seed2 | 174 | 36 | 90 | 300/300 |
| topotraj | 71 | 227 | 2 | 300/300 |
| agile_autonomy | 30 | 269 | 1 | 300/300 |
| mppi_reference17（已移出活动范围） | — | — | — | 0/300（不在活动范围；历史记录已归档） |

来源：[summary.json](../artifacts/benchmark_summary/summary.json)（活动范围口径，`status=outcome_coverage_complete`）。合计622成功、624碰撞、254超时；无效证据、重复主尝试和测量缺口均为0。失败终态属于已执行；MPPI 的跳过记录不是真实飞行失败，且不计入活动验收。

## 准入与身份

[runtime_validation.json](protocol_v1/runtime_validation.json)记录通过的后端、20个冻结运行文件哈希，以及准入消费的6个正式任务。驱动账本不含这6个任务，所以1794条账本记录不等于1794次已飞行。当前覆盖以summary为准，plan.json的pending=310是历史调度快照。

2026-10-13 发布勘误：`scripts/run_benchmark_matrix.py` 的机器默认解释器改为 `YOPO_ISAAC_PYTHON`（容器内启动行为不变），准入记录已加 `runtime_files_amendment` 透明标注旧/新哈希；其余 19 个冻结文件字节未变。既有 1500 槽飞行证据与准入阶段结果不受影响；后续任何再次改动运行时文件都会使准入失效（需重新准入）。

正式YOPO只接受对应种子50轮训练后、验证集选出且审计通过的权重。官方权重、Simple演示、开发展示和聚合微调实验均单独统计，不填入主矩阵。

`configs/benchmark_runtime/v1.json`保留准入前的声明状态和pending字段，属于冻结元数据；不能用它覆盖实际passed准入。TopoTraj有效建图范围、加速度上限和基线分布适配的公平性限制仍需保留。见[基准运行口径](../report/04_evaluation/04_基准运行配置冻结.md)。

## 汇总规则与真实缺口

成功、碰撞、超时、崩溃和越界保留在已执行分母；缺失任务为未知。重复主尝试或不合法证据会阻止无歧义汇总。成功率给Wilson区间，路径、安全、jerk分别报告全部尝试和成功样本。图表见[paper_figures](../artifacts/paper_figures)。

活动范围口径下 `summary.status=outcome_coverage_complete`、终审 `benchmark_matrix=verified`（6 项验收全部通过，见 [报告状态总览](../report/01_status/02_复现状态总览.md)）。参考[17] MPPI 于 2026-10-13 经用户决定移出活动范围：身份/全文与旧方案归档于 [report/90_archive/mppi](../report/90_archive/mppi/README.md) 与 [plan/90_decisions/archive_mppi](../plan/90_decisions/archive_mppi/README.md)；1800 槽超集记录归档于 [archive/protocol_v1_1800](archive/protocol_v1_1800)。

如需重新生成汇总，现有命令如下（会写回派生汇总，需确认这是当前工作目的）：

```powershell
docker compose --profile cpu-tools run --rm cpu-tools python3 scripts/aggregate_benchmarks.py
```

该脚本默认按 `active_scope_yopo_only.json` 汇总（活动范围）；需要复算历史 1800 超集口径时加 `--superset`。

本次发布整理没有重跑矩阵、没有新增飞行；活动范围汇总由既有飞行证据重新聚合生成。
