# 01 当前状态

更新：2026-10-12 ｜ 权威文件：[final_acceptance_audit.json](../../artifacts/environment/final_acceptance_audit.json)（机械验收审计，每项列出所检查的证据文件）

当前正式训练、运行时准入、专家比较、DAgger 微调和最终自训练展示已完成。正式矩阵已完成 1500/1800；缺少的 300 个槽位全部属于参考[17] MPPI。整体 `all_verified=false`。

## 终审 7 项

| 验收项 | 状态 | 说明 |
|---|---|---|
| three_seed_training | verified | 三个种子各 50 轮从头训练，全部通过逐轮严格审计 |
| expert_50_step_comparison | verified | 审计权重在独立离线测试集上的专家对照（三种子 + 随机初始化，全量样本） |
| baseline_native_validation | verified | 矩阵前的基线 CUDA/原生闭环准入（含 Agile CUDA parity） |
| mppi_reference17 | documented_gap | 未找到官方发布，协议记录为重实现需求（reference_only_no_official_release_found_reimplementation_required） |
| dagger_finetune | verified | 独立聚合数据集与微调检查点均完成 |
| benchmark_matrix | pending | completed=1500 / expected=1800、driver_failures=300、invalid_evidence=0、aggregate_status=incomplete |
| final_showcase_and_audit | verified | 50 轮权重展示可追溯到审计检查点，命令/证据审计通过 |

说明：plan.json 中的 `plan_pending=310` 和运行配置里的旧 pending 是历史快照；实际状态以准入、训练审计、DAgger 结果与 benchmark summary 为准。

## 未闭项与边界

- 300 槽缺口全部是 MPPI 未实现；决策选项见 [MPPI参考17身份与可得性](../../reports/MPPI参考17身份与可得性.md)。
- DAgger 微调已完成，但现有证据不支持“微调一定改善闭环成功率”；微调权重不进入原 1800 矩阵。
- 实机实验（论文 III-C）未复现；飞行结论均来自 Isaac 仿真闭环。
- 训练 verified 不等于所有飞行成功；verified 只表示该项有证据。

## 其他状态入口

- [复现状态总览](../../reports/复现状态总览.md)：由权威 JSON 生成，旧声明和计划仅作历史字段。
- [当前进度简报](../../reports/当前进度简报.md)：已完成项、真实缺口与主要产物。
- [benchmark summary](../../artifacts/benchmark_summary/summary.json)：矩阵聚合明细。
- [复现模块总图](../00_index/01_module_map.md)：模块级状态与论文对照入口。

