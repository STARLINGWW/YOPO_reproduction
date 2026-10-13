# MPPI 归档（archive_mppi）

标签：`historical / not_used_by_active_yopo_only_release`。

2026-10-13 用户决定：参考[17] MPPI 移出活动复现与验收范围（见 [DEC-20261013-01](../DEC-20261013-01_MPPI移出活动范围与YOPO-only归档.md)）。本目录保留当时的 A/B 方案与预演补丁，仅作历史决策资料：

- `optionA_mppi_reference17_plan.md`：按论文补齐 300 槽的实施计划（未执行）。
- `optionB_matrix_scope_proposal.md`、`optionB_matrix_scope_implementation_report.md`、`optionB_matrix_scope_implementation.patch`：把矩阵覆盖冻结为「已验证后端 + 显式排除」的提案与预演补丁；其方向已按 YOPO-only 活动范围落地（实现见 `benchmarks/protocol_v1/active_scope_yopo_only.json` 与 `scripts/aggregate_benchmarks.py`）。

这些文件不代表当前待办；当前范围与状态见 report/00_index 与 report/01_status。
