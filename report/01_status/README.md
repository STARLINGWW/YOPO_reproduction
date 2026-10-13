# 01 当前状态

更新：2026-10-13 ｜ 权威文件：[final_acceptance_audit.json](../../artifacts/environment/final_acceptance_audit.json)（机械验收审计，每项列出所检查的证据文件）

当前正式训练、运行时准入、专家比较、DAgger 微调和最终自训练展示已完成；YOPO-only 活动矩阵 1,500/1,500 全部收官。终审 **6 verified、0 documented_gap、0 pending、all_verified=true**；参考[17] MPPI 已移出活动范围并归档（历史超集记录见 [benchmarks/archive](../../benchmarks/archive/README.md)）。

## 终审 6 项（YOPO-only 活动范围）

| 验收项 | 状态 | 说明 |
|---|---|---|
| three_seed_training | verified | 三个种子各 50 轮从头训练，全部通过逐轮严格审计 |
| expert_50_step_comparison | verified | 审计权重在独立离线测试集上的专家对照（三种子 + 随机初始化，全量样本） |
| baseline_native_validation | verified | 矩阵前的基线 CUDA/原生闭环准入（含 Agile CUDA parity） |
| dagger_finetune | verified | 独立聚合数据集与微调检查点均完成 |
| benchmark_matrix | verified | completed=1500 / expected=1500（活动范围口径）、invalid_evidence=0、duplicates=0、aggregate_status=outcome_coverage_complete |
| final_showcase_and_audit | verified | 50 轮权重展示可追溯到审计检查点，命令/证据审计通过 |

说明：plan.json 中的 `plan_pending=310` 和运行配置里的旧 pending 是历史快照；实际状态以准入、训练审计、DAgger 结果与 benchmark summary 为准。

## 未闭项与边界

- 参考[17] MPPI 于 2026-10-13 移出活动范围（历史归档：[report/90_archive/mppi](../90_archive/mppi/README.md)、[plan/90_decisions/archive_mppi](../../plan/90_decisions/archive_mppi/README.md)）。
- DAgger 微调已完成，但现有证据不支持“微调一定改善闭环成功率”；微调权重不进入原 1800 矩阵。
- 实机实验（论文 III-C）未复现；飞行结论均来自 Isaac 仿真闭环。
- 训练 verified 不等于所有飞行成功；verified 只表示该项有证据。

## 其他状态入口

- [复现状态总览](02_复现状态总览.md)：由权威 JSON 生成，旧声明和计划仅作历史字段。
- [当前进度简报](01_当前进度简报.md)：已完成项、真实缺口与主要产物。
- [benchmark summary](../../artifacts/benchmark_summary/summary.json)：矩阵聚合明细。
- [复现模块总图](../00_index/01_module_map.md)：模块级状态与论文对照入口。

