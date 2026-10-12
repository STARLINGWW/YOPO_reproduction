# 固定任务与正式基准结果

更新：2026-10-08。固定任务和运行时文件已冻结，`protocol_v1/runtime_validation.json`已存在且status=passed，准入后端为YOPO、TopoTraj、Agile。**正式矩阵已执行1,500/1,800；剩余300为参考[17] MPPI未执行槽位。**

## 任务与覆盖

20张独立地图、两档密度（1/30、1/20）、五档速度（2/4/6/8/10m/s）、每条件30次，每模型300次。三份自训练YOPO及三种外部基线共1800个槽位。每条件前10次是论文规模子集，不能与all30重复相加。

| 模型 | 成功 | 碰撞 | 超时 | 已执行/计划 |
|---|---:|---:|---:|---:|
| yopo_seed0 | 184 | 42 | 74 | 300/300 |
| yopo_seed1 | 163 | 50 | 87 | 300/300 |
| yopo_seed2 | 174 | 36 | 90 | 300/300 |
| topotraj | 71 | 227 | 2 | 300/300 |
| agile_autonomy | 30 | 269 | 1 | 300/300 |
| mppi_reference17 | — | — | — | 0/300 |

来源：[summary.json](../artifacts/benchmark_summary/summary.json)。合计622成功、624碰撞、254超时；无效证据、重复主尝试和测量缺口均为0。失败终态属于已执行；MPPI跳过记录不是真实飞行失败。

## 准入与身份

[runtime_validation.json](protocol_v1/runtime_validation.json)记录通过的后端、20个冻结运行文件哈希，以及准入消费的6个正式任务。驱动账本不含这6个任务，所以1794条账本记录不等于1794次已飞行。当前覆盖以summary为准，plan.json的pending=310是历史调度快照。

正式YOPO只接受对应种子50轮训练后、验证集选出且审计通过的权重。官方权重、Simple演示、开发展示和聚合微调实验均单独统计，不填入主矩阵。

`configs/benchmark_runtime/v1.json`保留准入前的声明状态和pending字段，属于冻结元数据；不能用它覆盖实际passed准入。TopoTraj有效建图范围、加速度上限和基线分布适配的公平性限制仍需保留。见[基准运行口径](../report/04_evaluation/04_基准运行配置冻结.md)。

## 汇总规则与真实缺口

成功、碰撞、超时、崩溃和越界保留在已执行分母；缺失任务为未知。重复主尝试或不合法证据会阻止无歧义汇总。成功率给Wilson区间，路径、安全、jerk分别报告全部尝试和成功样本。图表见[paper_figures](../artifacts/paper_figures)。

原1800协议未改变，summary.status仍incomplete、benchmark_matrix仍pending。MPPI全文已归档，但基线实现和300次飞行未完成。重跑矩阵仍会跳过这一后端，不能靠重复运行解决验收缺口。A/B/C方案见[MPPI说明](../report/04_evaluation/05_MPPI参考17身份与可得性.md)。

如需重新生成汇总，现有命令如下（会写回派生汇总，需确认这是当前工作目的）：

```powershell
docker compose --profile cpu-tools run --rm cpu-tools python3 scripts/aggregate_benchmarks.py
```

本次文档整理只读取已有汇总，没有重新运行矩阵或聚合飞行数据。
